# -*- coding: utf-8 -*-
"""GET /demo/{overview,seatmap,analytics} (read-only) + POST reset/forecasts-refresh.

Tích hợp H10-H14: refresh dùng logic BE2 thật (`forecast.refresh_forecast` — bump
version, giữ run_id/che_do_gia); analytics trả forecast per-segment + bid theo leg;
overview tính doanh thu/pax-km/decision thật từ DB thay vì placeholder 0.
"""
import json
from datetime import date

from fastapi import APIRouter

from ..allocation import cache as allocation_cache
from ..audit import log as audit_log
from ..forecast import forecast, network
from ..state.db import get_connection
from .deps import SEED_DIR, get_clock, get_state_manager
from .schemas import ResetRequest

router = APIRouter(tags=["demo"])

_SCENARIO = json.loads((SEED_DIR / "scenario.json").read_text(encoding="utf-8"))
SEAT_CLASS = _SCENARIO.get("seat_class", "NGOI_MEM_DH")


def _seg_counts(seatmap: dict) -> tuple[dict[int, int], dict[int, int], int]:
    """(sold_by_segment [non-FREE], free_by_segment, n_seats) từ một snapshot seatmap."""
    n_segments = network.N_SEGMENTS
    sold = {s: 0 for s in range(1, n_segments + 1)}
    free = {s: 0 for s in range(1, n_segments + 1)}
    for states in seatmap["seats"].values():
        for seg_str, status in states.items():
            seg = int(seg_str)
            if status == "FREE":
                free[seg] += 1
            else:
                sold[seg] += 1
    return sold, free, len(seatmap["seats"])


def _latest_forecast_rows(cur, service_run_id: str) -> tuple[list[tuple], int]:
    cur.execute(
        """SELECT forecast_demand, confidence_score, forecast_version FROM demand_forecast
           WHERE service_run_id=%s
             AND forecast_version=(SELECT COALESCE(MAX(forecast_version),1)
                                   FROM demand_forecast WHERE service_run_id=%s)
           ORDER BY id""",
        (service_run_id, service_run_id),
    )
    rows = cur.fetchall()
    return rows, (rows[0][2] if rows else 1)


@router.post("/demo/scenarios/{scenario_id}/reset")
def reset_scenario(scenario_id: str, body: ResetRequest = ResetRequest()):
    ssm = get_state_manager()
    result = ssm.reset_scenario(SEED_DIR)
    allocation_cache.refresh(result["service_run_id"])
    return {"data": result, "message": "Scenario reset successfully"}


@router.post("/demo/forecasts/refresh")
def refresh_forecast(body: dict):
    service_run_id = body.get("service_run_id", _SCENARIO["service_run_id"])
    ssm = get_state_manager()
    clock = get_clock()

    sold, _free, n_seats = _seg_counts(ssm.get_seatmap(service_run_id))
    capacity = {s: n_seats for s in sold}
    service_date = date.fromisoformat(_SCENARIO["service_date"])
    days_to_departure = float(max((service_date - clock.now().date()).days, 0))

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(MAX(forecast_version),1) FROM demand_forecast WHERE service_run_id=%s",
            (service_run_id,),
        )
        prev_version = cur.fetchone()[0]
        prev = {"forecast_version": prev_version, "service_run_id": service_run_id,
                "che_do_gia": _SCENARIO.get("che_do_gia", "AI")}
        new = forecast.refresh_forecast(prev, sold, capacity, days_to_departure)
        for seg in new["segments"]:
            cur.execute(
                """INSERT INTO demand_forecast
                   (service_run_id, origin_station_id, dest_station_id, seat_class,
                    forecast_demand, confidence_score, forecast_version)
                   VALUES (%s,NULL,NULL,%s,%s,%s,%s)""",
                (service_run_id, SEAT_CLASS, round(seg["forecast_remaining"]),
                 seg["confidence"], new["forecast_version"]),
            )
    conn.commit()
    allocation_cache.refresh(service_run_id)

    # P7.5 — persist divergence/alert của lần refresh này (trước bị log rồi bỏ, xem
    # forecast.py::refresh_forecast); GET /demo/overview đọc lại bản mới nhất để cảnh báo.
    audit_log.persist(conn, {"loai": "FORECAST", "input": {"forecast_version": new["forecast_version"]},
                             "output": new["drift"],
                             "explain": f"{len(new['drift']['alerts'])} đoạn lệch dự báo ≥{new['drift']['threshold']:.0%}",
                             "model_version": "1.0"}, service_run_id)
    return {"message": "Forecast updated", "data": {"forecast_version": new["forecast_version"],
                                                     "drift_alerts": new["drift"]["alerts"]}}


@router.get("/demo/overview")
def get_overview(service_run_id: str):
    ssm = get_state_manager()
    sold, free, n_seats = _seg_counts(ssm.get_seatmap(service_run_id))
    occupancy = {s: (sold[s] / n_seats if n_seats else 0.0) for s in sold}
    overall = sum(occupancy.values()) / len(occupancy) if occupancy else 0.0
    bottlenecks = sorted(occupancy.items(), key=lambda kv: -kv[1])[:3]
    underused = sorted(occupancy.items(), key=lambda kv: kv[1])[:3]

    passenger_km = sum(sold[s] * network.LEG_DISTANCE_KM[s] for s in sold)
    empty_seat_km = sum(free[s] * network.LEG_DISTANCE_KM[s] for s in free)

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT COALESCE(SUM(o.final_price_vnd),0)
               FROM booking b JOIN seat_hold sh ON b.hold_id=sh.hold_id
                              JOIN offer o ON sh.offer_id=o.offer_id
               WHERE b.status='CONFIRMED' AND o.service_run_id=%s""",
            (service_run_id,),
        )
        total_revenue = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE result='REJECT') FROM decision_record")
        n_decisions, n_reject = cur.fetchone()
        cur.execute(
            """SELECT decision_id, result, final_price_vnd, explanation_code, created_at
               FROM decision_record ORDER BY created_at DESC LIMIT 5""",
        )
        recent = [{"decision_id": r[0], "result": r[1], "final_price_vnd": r[2],
                   "explanation_code": r[3], "created_at": r[4].isoformat()} for r in cur.fetchall()]
        # P7.5 — cảnh báo lệch dự báo của lần refresh gần nhất (rỗng nếu chưa refresh lần nào)
        cur.execute(
            """SELECT output FROM proposal_log WHERE service_run_id=%s AND loai='FORECAST'
               ORDER BY id DESC LIMIT 1""",
            (service_run_id,),
        )
        drift_row = cur.fetchone()
        drift_alerts = drift_row[0].get("alerts", []) if drift_row else []
    conn.commit()

    return {"data": {
        "overall_occupancy": round(overall, 3),
        "total_revenue_vnd": total_revenue,
        "empty_seat_km": round(empty_seat_km, 1),
        "passenger_km": round(passenger_km, 1),
        "false_sold_out_rate": round(n_reject / n_decisions, 3) if n_decisions else 0.0,
        "bottlenecks": [{"segment_id": s, "occupancy": round(o, 3)} for s, o in bottlenecks],
        "underused": [{"segment_id": s, "occupancy": round(o, 3)} for s, o in underused],
        "recent_decisions": recent,
        "drift_alerts": drift_alerts,
    }}


@router.get("/demo/seatmap")
def get_seatmap(service_run_id: str):
    ssm = get_state_manager()
    result = ssm.get_seatmap(service_run_id)
    seats_out = []
    for seat_id, states in sorted(result["seats"].items()):
        seats_out.append({"seat_id": seat_id, "seat_class": SEAT_CLASS, "states": states})
    return {"data": {"matrix_version": result["matrix_version"], "seats": seats_out}}


@router.get("/demo/analytics")
def get_analytics(service_run_id: str):
    ssm = get_state_manager()
    sold, free, n_seats = _seg_counts(ssm.get_seatmap(service_run_id))

    conn = get_connection()
    with conn.cursor() as cur:
        rows, forecast_version = _latest_forecast_rows(cur, service_run_id)
    conn.commit()
    forecast_by_seg = {i + 1: float(r[0]) for i, r in enumerate(rows)}
    confidence_by_seg = {i + 1: float(r[1]) if r[1] is not None else None
                         for i, r in enumerate(rows)}

    forecasts = [
        {"segment_id": s, "forecast_remaining": forecast_by_seg.get(s),
         "confidence": confidence_by_seg.get(s)}
        for s in sorted(sold)
    ]
    segment_loads = [
        {"segment_id": s, "occupancy": round(sold[s] / n_seats, 3) if n_seats else 0.0,
         "remaining_capacity": free[s]}
        for s in sorted(sold)
    ]
    # DLP thật qua cache — chỉ có khi reset/refresh-forecast đã chạy cho version này;
    # cache miss (chưa refresh) => hiển thị 0, KHÔNG bịa công thức fallback (endpoint
    # đọc-only, không phải quyết định giá — invariant "không fallback" áp cho /offers).
    cached = allocation_cache.get(service_run_id, get_state_manager().get_matrix_version(service_run_id),
                                  forecast_version)
    bid_by_seg_cached = ({row["khu_gian_id"]: row["bid_price"] for row in cached["lf_theo_doan"]}
                         if cached else {})
    allocations = [
        {"segment_id": s, "bid_price_vnd": bid_by_seg_cached.get(s, 0)}
        for s in sorted(sold)
    ]
    return {"data": {"forecast_version": forecast_version, "forecasts": forecasts,
                     "segment_loads": segment_loads, "allocations": allocations}}

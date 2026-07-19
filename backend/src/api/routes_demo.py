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
from ..forecast.runtime import ensure_model_forecast
from ..forecast.topology import get_run_topology
from ..state.db import get_connection
from .deps import SEED_DIR, get_clock, get_state_manager
from .schemas import ResetRequest

router = APIRouter(tags=["demo"])

_SCENARIO = json.loads((SEED_DIR / "scenario.json").read_text(encoding="utf-8"))
SEAT_CLASS = _SCENARIO.get("seat_class", "NGOI_MEM_DH")


def _seg_counts(seatmap: dict) -> tuple[dict[int, int], dict[int, int], int]:
    """(sold_by_segment [non-FREE], free_by_segment, n_seats) từ một snapshot seatmap.
    Số chặng suy TRỰC TIẾP từ seatmap của run (không khóa cứng golden 7 chặng)."""
    sold: dict[int, int] = {}
    free: dict[int, int] = {}
    for states in seatmap["seats"].values():
        for seg_str, status in states.items():
            seg = int(seg_str)
            sold.setdefault(seg, 0)
            free.setdefault(seg, 0)
            if status == "FREE":
                free[seg] += 1
            else:
                sold[seg] += 1
    return sold, free, len(seatmap["seats"])


def _leg_km(cur, service_run_id: str) -> dict[int, float]:
    """segment_id 1-based -> chiều dài leg (km), lấy từ train_stop + station của run.
    Rỗng nếu thiếu topology; caller coi khoảng cách = 0 (không khóa cứng golden)."""
    cur.execute(
        """SELECT s.ly_trinh_km FROM train_stop ts
             JOIN service_run sr ON ts.train_id = sr.train_id
             JOIN station s ON ts.station_id = s.station_id
            WHERE sr.service_run_id = %s ORDER BY ts.stop_sequence""",
        (service_run_id,),
    )
    km = [float(r[0]) for r in cur.fetchall()]
    return {i + 1: abs(km[i + 1] - km[i]) for i in range(len(km) - 1)}


def _latest_forecast_rows(cur, service_run_id: str) -> tuple[list[tuple], int]:
    cur.execute(
        """SELECT origin_station_id, dest_station_id, seat_class,
                  forecast_demand, confidence_score, forecast_version
             FROM demand_forecast
           WHERE service_run_id=%s
             AND forecast_version=(SELECT COALESCE(MAX(forecast_version),1)
                                   FROM demand_forecast WHERE service_run_id=%s)
           ORDER BY id""",
        (service_run_id, service_run_id),
    )
    rows = cur.fetchall()
    return rows, (rows[0][5] if rows else 1)


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


@router.get("/demo/runs")
def list_runs(limit: int = 500, q: str | None = None):
    """Danh sách chuyến thật trong DB cho run-picker (thay golden run cứng)."""
    conn = get_connection()
    with conn.cursor() as cur:
        sql = ("SELECT service_run_id, train_id, service_date, direction, status "
               "FROM service_run WHERE service_date >= "
               "(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Ho_Chi_Minh')::DATE")
        params: list = []
        if q:
            sql += " AND (service_run_id ILIKE %s OR train_id ILIKE %s)"
            params += [f"%{q}%", f"%{q}%"]
        sql += " ORDER BY service_date, service_run_id LIMIT %s"
        params.append(limit)
        cur.execute(sql, params)
        runs = [{"service_run_id": r[0], "train_id": r[1],
                 "service_date": r[2].isoformat(), "direction": r[3], "status": r[4]}
                for r in cur.fetchall()]
    conn.commit()
    return {"data": {"runs": runs}}


@router.get("/demo/stations")
def list_stations():
    """Danh mục ga (id -> tên) cho nhãn hiển thị, thay STATIONS hardcode ở FE."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT station_id, station_name, ly_trinh_km FROM station ORDER BY ly_trinh_km")
        stations = [{"station_id": r[0], "station_name": r[1], "ly_trinh_km": float(r[2])}
                    for r in cur.fetchall()]
    conn.commit()
    return {"data": {"stations": stations}}


@router.get("/demo/runs/{service_run_id}/stops")
def get_run_stops(service_run_id: str):
    """Ga dừng thực tế theo thứ tự của MỘT chuyến — cho FE dựng nhãn chặng/ga động
    thay vì STATIONS/SEGMENTS cứng theo golden network (8 ga/7 chặng)."""
    topology = get_run_topology(service_run_id)
    stops = [{"stop_sequence": station["sequence"], "station_id": station["id"],
              "station_name": station["name"]} for station in topology["stations"]]
    return {"data": {"stops": stops}}


@router.get("/demo/overview")
def get_overview(service_run_id: str):
    ssm = get_state_manager()
    sold, free, n_seats = _seg_counts(ssm.get_seatmap(service_run_id))
    occupancy = {s: (sold[s] / n_seats if n_seats else 0.0) for s in sold}
    overall = sum(occupancy.values()) / len(occupancy) if occupancy else 0.0
    bottlenecks = sorted(occupancy.items(), key=lambda kv: -kv[1])[:3]
    underused = sorted(occupancy.items(), key=lambda kv: kv[1])[:3]

    conn = get_connection()
    with conn.cursor() as cur:
        leg_km = _leg_km(cur, service_run_id)
        passenger_km = sum(sold[s] * leg_km.get(s, 0.0) for s in sold)
        empty_seat_km = sum(free[s] * leg_km.get(s, 0.0) for s in free)
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
        # ponytail: decision_record has no service_run_id/offer_id FK (V1 schema gap, see
        # seat_state_manager.py:340) — recent_decisions is global across all runs, not
        # scoped to this one. Proper fix needs a migration + backfill; out of scope here.
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
def get_seatmap(service_run_id: str, seat_class: str = SEAT_CLASS):
    ssm = get_state_manager()
    result = ssm.get_seatmap(service_run_id, seat_class)
    seats_out = []
    for seat_id, states in sorted(result["seats"].items()):
        seats_out.append({"seat_id": seat_id, "seat_class": seat_class, "states": states})
    return {"data": {"matrix_version": result["matrix_version"], "seats": seats_out}}


@router.get("/demo/analytics")
def get_analytics(service_run_id: str):
    ensure_model_forecast(service_run_id)
    topology = get_run_topology(service_run_id)
    ssm = get_state_manager()
    sold, free, n_seats = _seg_counts(ssm.get_seatmap(service_run_id))

    conn = get_connection()
    with conn.cursor() as cur:
        rows, forecast_version = _latest_forecast_rows(cur, service_run_id)
    conn.commit()
    forecast_by_seg = {segment: 0.0 for segment in sold}
    confidence_values = {segment: [] for segment in sold}
    station_index = {station["id"]: index for index, station in enumerate(topology["stations"])}
    if rows and rows[0][0] is not None:
        for origin, dest, _seat_class, demand, confidence, _version in rows:
            start, end = station_index.get(origin), station_index.get(dest)
            if start is None or end is None or start >= end:
                continue
            for segment in range(start + 1, end + 1):
                forecast_by_seg[segment] += float(demand)
                if confidence is not None:
                    confidence_values[segment].append(float(confidence))
    else:
        for index, row in enumerate(rows):
            segment = index + 1
            if segment in forecast_by_seg:
                forecast_by_seg[segment] = float(row[3])
                if row[4] is not None:
                    confidence_values[segment].append(float(row[4]))
    confidence_by_seg = {
        segment: (sum(values) / len(values) if values else None)
        for segment, values in confidence_values.items()
    }

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

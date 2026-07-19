# -*- coding: utf-8 -*-
"""GET /demo/{overview,seatmap,analytics} (read-only) + POST reset/forecasts-refresh.

Tích hợp H10-H14: refresh dùng logic BE2 thật (`forecast.refresh_forecast` — bump
version, giữ run_id/che_do_gia); analytics trả forecast per-segment + bid theo leg;
overview tính doanh thu/pax-km/decision thật từ DB thay vì placeholder 0.
"""
import json
import re
from datetime import date

from fastapi import APIRouter, HTTPException

from ..allocation import cache as allocation_cache
from ..audit import log as audit_log
from ..forecast import forecast, network
from ..state.db import get_connection
from .deps import SEED_DIR, get_clock, get_state_manager
from .schemas import ResetRequest

router = APIRouter(tags=["demo"])

_SCENARIO = json.loads((SEED_DIR / "scenario.json").read_text(encoding="utf-8"))
SEAT_CLASS = _SCENARIO.get("seat_class", "NGOI_MEM_DH")

# Mock-loaded seat_ids (backend/scripts/load_mock_from_dataset.py::seat_id_of) are
# "<agg_class>-<4-digit-num>" and carry the real class in the prefix; golden-scenario
# seat_ids ("C01-S017") don't match this shape, so they fall back to SEAT_CLASS.
_SEAT_CLASS_RE = re.compile(r"^(.+)-(\d{4})$")


def _seat_class_of(seat_id: str) -> str:
    m = _SEAT_CLASS_RE.match(seat_id)
    return m.group(1) if m else SEAT_CLASS


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


@router.get("/demo/runs")
def list_runs(limit: int = 500, q: str | None = None):
    """Danh sách chuyến thật trong DB cho run-picker (thay golden run cứng)."""
    conn = get_connection()
    with conn.cursor() as cur:
        sql = ("SELECT service_run_id, train_id, service_date, direction, status "
               "FROM service_run")
        params: list = []
        if q:
            sql += " WHERE service_run_id ILIKE %s OR train_id ILIKE %s"
            params += [f"%{q}%", f"%{q}%"]
        # DESC: chuyến mới/ngày xa nhất lên đầu — nếu ASC, chuyến vừa tạo (ngày tương lai)
        # rơi xuống cuối và bị LIMIT cắt mất khỏi run-picker.
        sql += " ORDER BY service_date DESC, service_run_id DESC LIMIT %s"
        params.append(limit)
        cur.execute(sql, params)
        runs = [{"service_run_id": r[0], "train_id": r[1],
                 "service_date": r[2].isoformat(), "direction": r[3], "status": r[4]}
                for r in cur.fetchall()]
    conn.commit()
    return {"data": {"runs": runs}}


@router.post("/demo/runs")
def create_run(body: dict):
    """Tạo chuyến mới với toàn bộ ghế FREE — chọn tàu + ngày chạy tương lai.
    Sơ đồ ghế/số chặng/bảng giá nhân bản từ chuyến mẫu (run cùng tàu nhiều ghế nhất)
    nên chuyến mới bán được ngay; chưa seed forecast/DLP (analytics hiện 0 cho tới khi
    bấm 'Làm mới dự báo') — đúng hành vi 'cache miss => 0' của route đọc-only."""
    train_id = (body.get("train_id") or "").strip()
    service_date = (body.get("service_date") or "").strip()
    if not train_id or not service_date:
        raise HTTPException(422, "train_id và service_date là bắt buộc")
    try:
        date.fromisoformat(service_date)
    except ValueError:
        raise HTTPException(422, "service_date phải dạng YYYY-MM-DD")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM train WHERE train_id=%s", (train_id,))
            if not cur.fetchone():
                raise HTTPException(404, f"Không có tàu {train_id}")
            # chuyến mẫu: cùng tàu, nhiều ghế nhất -> lấy tập ghế + số chặng + hướng + bảng giá
            cur.execute(
                """SELECT s.service_run_id, sr.direction FROM seat_segment_state s
                     JOIN service_run sr ON s.service_run_id=sr.service_run_id
                    WHERE sr.train_id=%s
                    GROUP BY s.service_run_id, sr.direction
                    ORDER BY COUNT(DISTINCT s.seat_id) DESC LIMIT 1""",
                (train_id,),
            )
            src = cur.fetchone()
            if not src:
                raise HTTPException(422, f"Tàu {train_id} chưa có chuyến mẫu để dựng sơ đồ ghế")
            src_run, direction = src
            cur.execute("SELECT DISTINCT seat_id FROM seat_segment_state WHERE service_run_id=%s", (src_run,))
            seat_ids = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT COALESCE(MAX(segment_id),0) FROM seat_segment_state WHERE service_run_id=%s", (src_run,))
            n_segments = cur.fetchone()[0]

            base = f"{train_id}_{service_date}_NEW"
            new_id, i = base, 2
            while True:
                cur.execute("SELECT 1 FROM service_run WHERE service_run_id=%s", (new_id,))
                if not cur.fetchone():
                    break
                new_id, i = f"{base}{i}", i + 1

            cur.execute(
                """INSERT INTO service_run (service_run_id, train_id, service_date, direction, status, matrix_version)
                   VALUES (%s,%s,%s,%s,'ACTIVE',1)""",
                (new_id, train_id, service_date, direction),
            )
            cur.executemany(
                """INSERT INTO seat_segment_state (service_run_id, seat_id, segment_id, status, version)
                   VALUES (%s,%s,%s,'FREE',1)""",
                [(new_id, sid, seg) for sid in seat_ids for seg in range(1, n_segments + 1)],
            )
            cur.execute(
                """INSERT INTO fare_product (service_run_id, origin_station_id, dest_station_id, seat_class, base_fare_vnd, version)
                   SELECT %s, origin_station_id, dest_station_id, seat_class, base_fare_vnd, version
                     FROM fare_product WHERE service_run_id=%s""",
                (new_id, src_run),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"data": {"service_run_id": new_id, "train_id": train_id, "service_date": service_date,
                     "direction": direction, "seats": len(seat_ids), "segments": n_segments},
            "message": "Trip created"}


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
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT ts.stop_sequence, ts.station_id, s.station_name
                 FROM train_stop ts
                 JOIN service_run sr ON ts.train_id = sr.train_id
                 JOIN station s ON ts.station_id = s.station_id
                WHERE sr.service_run_id = %s ORDER BY ts.stop_sequence""",
            (service_run_id,),
        )
        stops = [{"stop_sequence": r[0], "station_id": r[1], "station_name": r[2]} for r in cur.fetchall()]
    conn.commit()
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
def get_seatmap(service_run_id: str):
    ssm = get_state_manager()
    result = ssm.get_seatmap(service_run_id)
    seats_out = []
    for seat_id, states in sorted(result["seats"].items()):
        seats_out.append({"seat_id": seat_id, "seat_class": _seat_class_of(seat_id), "states": states})
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

# -*- coding: utf-8 -*-
"""POST /offers — same-seat gap scan + pricing + demo bid-price approximation.
KHÔNG giữ ghế (đó là việc của /holds). Chỉ đọc seed/DB — không chạm dữ liệu
chấm điểm offline (Master §2.1, CI gate cấm mọi tham chiếu tới nó trong src/).

Pricing/bid ở đây là bản RÚT GỌN cho phiên làm việc solo (không có BE2/BE3):
base fare đọc từ seed/fare_products (qua fare_product table), clip floor/ceiling
ratio trên F0 (đúng thứ tự luật), bid_price = "demo bid-price approximation"
(round_to_1k(yield_per_km * distance * scarcity)) — KHÔNG claim EMSR-b.
"""
import uuid
from datetime import timedelta

from fastapi import APIRouter, Header

from ..state.db import get_connection
from ..state.errors import AllocationRejected, NoSameSeatOption, PolicyUnavailable
from .deps import get_clock, get_state_manager
from .schemas import OfferRequest

router = APIRouter(tags=["booking"])

# Golden scenario stations — khớp scripts/build_seed.py (không seed vào DB
# station table trong phiên rút gọn này; đủ cho golden path 8 ga cố định).
STATION_ORDER = ["HNO", "NBI", "THO", "VIN", "DHO", "HUE", "DNA", "SGO"]
STATION_KM = {"HNO": 0.0, "NBI": 115.0, "THO": 175.0, "VIN": 319.0,
              "DHO": 522.0, "HUE": 688.0, "DNA": 791.4, "SGO": 1726.0}
OFFER_TTL_SECONDS = 300

REF_YIELD_PLACEHOLDER = 700  # VND/km — demo bid-price approximation only
P_LOW, P_HIGH = 0.6, 1.0


def seg_range(origin: str, dest: str) -> tuple[int, int]:
    if origin not in STATION_ORDER or dest not in STATION_ORDER:
        raise NoSameSeatOption("Ga ngoài tuyến tàu", {"origin": origin, "dest": dest})
    i, j = STATION_ORDER.index(origin), STATION_ORDER.index(dest)
    if i >= j:
        raise NoSameSeatOption("origin phải trước dest theo lý trình", {"origin": origin, "dest": dest})
    return i + 1, j  # 1-based segment_id: segment k phục vụ station[k-1]->station[k]


def clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def round_1k(x: float) -> int:
    return int(round(x / 1000.0)) * 1000


@router.post("/offers", status_code=201)
def create_offer(req: OfferRequest):
    seg_from, seg_to = seg_range(req.origin_station_id, req.dest_station_id)
    ssm = get_state_manager()
    clock = get_clock()

    seat_id = ssm.find_continuous_same_seat(req.service_run_id, seg_from, seg_to)
    if not seat_id:
        raise NoSameSeatOption(
            "Không tìm được ghế liên tục cho hành trình",
            {"origin": req.origin_station_id, "dest": req.dest_station_id},
        )
    reused_gap = (seg_to - seg_from) >= 1

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT base_fare_vnd FROM fare_product
               WHERE service_run_id=%s AND origin_station_id=%s AND dest_station_id=%s AND seat_class=%s
               ORDER BY version DESC LIMIT 1""",
            (req.service_run_id, req.origin_station_id, req.dest_station_id, req.seat_class),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise PolicyUnavailable("Chưa có fare_product cho O-D này", {})
        base_fare = row[0]

        cur.execute(
            """SELECT floor_ratio, ceiling_ratio, policy_version FROM pricing_policy
               WHERE is_active=TRUE ORDER BY policy_id DESC LIMIT 1""",
        )
        prow = cur.fetchone()
        if not prow:
            conn.rollback()
            raise PolicyUnavailable("Chưa có pricing policy được approve", {})
        floor_ratio, ceiling_ratio, policy_version = prow

        cur.execute(
            """SELECT forecast_demand, forecast_version FROM demand_forecast
               WHERE service_run_id=%s AND seat_class=%s ORDER BY id LIMIT 7""",
            (req.service_run_id, req.seat_class),
        )
        forecast_result = cur.fetchall()
        forecast_rows = {i + 1: r[0] for i, r in enumerate(forecast_result)}
        forecast_version = forecast_result[0][1] if forecast_result else 1
        cur.execute("SELECT matrix_version FROM service_run WHERE service_run_id=%s", (req.service_run_id,))
        mv_row = cur.fetchone()
        matrix_version = mv_row[0] if mv_row else 1
    conn.commit()

    seatmap = ssm.get_seatmap(req.service_run_id)
    remaining_by_seg: dict[int, int] = {s: 0 for s in range(seg_from, seg_to + 1)}
    for states in seatmap["seats"].values():
        for seg_str, status in states.items():
            seg = int(seg_str)
            if seg_from <= seg <= seg_to and status == "FREE":
                remaining_by_seg[seg] += 1

    bid_by_segment = {}
    for seg in range(seg_from, seg_to + 1):
        o_id, d_id = STATION_ORDER[seg - 1], STATION_ORDER[seg]
        dist = STATION_KM[d_id] - STATION_KM[o_id]
        remaining_cap = max(remaining_by_seg.get(seg, 0), 1)
        forecast_remaining = forecast_rows.get(seg, remaining_cap * 0.6)
        pressure = forecast_remaining / remaining_cap
        scarcity = clip((pressure - P_LOW) / (P_HIGH - P_LOW), 0.0, 1.0)
        bid_by_segment[str(seg)] = round_1k(REF_YIELD_PLACEHOLDER * dist * scarcity)
    bid_total = sum(bid_by_segment.values())

    gia_niem_yet = clip(base_fare, base_fare * floor_ratio, base_fare * ceiling_ratio)
    gia_cuoi = round_1k(gia_niem_yet)  # không CSXH trong golden path mặc định (khách thường)

    decision = "ACCEPT"
    if gia_cuoi < bid_total:
        decision = "REJECT"

    offer_id = f"offer_{uuid.uuid4().hex[:12]}"
    decision_record_id = f"dr_{uuid.uuid4().hex[:12]}"
    expires_at = clock.now() + timedelta(seconds=OFFER_TTL_SECONDS)
    seat_plan = [{
        "seat_id": seat_id, "segment_from": seg_from, "segment_to": seg_to,
        "reused_gap": reused_gap, "requires_seat_change": False,
    }]

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO offer (offer_id, service_run_id, matrix_version, forecast_version, policy_version,
                                   decision, seat_plan, final_price_vnd, expires_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (offer_id, req.service_run_id, matrix_version, forecast_version, policy_version,
             decision, __import__("json").dumps(seat_plan), gia_cuoi, expires_at),
        )
        cur.execute(
            """INSERT INTO decision_record (decision_id, result, base_fare_vnd, ai_suggested_price_vnd,
                                             final_price_vnd, bid_price_total_vnd, bid_price_breakdown, actor)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'system')""",
            (decision_record_id, decision, base_fare, round_1k(gia_niem_yet), gia_cuoi, bid_total,
             __import__("json").dumps(bid_by_segment)),
        )
    conn.commit()

    if decision == "REJECT":
        raise AllocationRejected(
            "Giá vé không bù đủ chi phí cơ hội các đoạn chiếm dụng",
            {"final_price_vnd": gia_cuoi, "bid_price_total_vnd": bid_total, "decision_record_id": decision_record_id},
        )

    return {"data": {
        "offer_id": offer_id,
        "service_run_id": req.service_run_id,
        "matrix_version": matrix_version,
        "forecast_version": forecast_version,
        "policy_version": policy_version,
        "decision": decision,
        "seat_plan": seat_plan,
        "pricing": {
            "gia_goc_vnd": base_fare,
            "gia_niem_yet_vnd": round_1k(gia_niem_yet),
            "gia_cuoi_vnd": gia_cuoi,
            "rules_fired": [],
            "clamped": round_1k(gia_niem_yet) != base_fare,
            "che_do_gia": "AI",
        },
        "bid": {"total_vnd": bid_total, "by_segment": bid_by_segment},
        "decision_record_id": decision_record_id,
        "expires_at": expires_at.isoformat(),
    }}

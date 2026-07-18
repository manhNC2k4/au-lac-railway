# -*- coding: utf-8 -*-
"""POST /holds (atomic CAS) + POST /bookings/{hold_id}/confirm (idempotent, no re-price)."""
import json

from fastapi import APIRouter, Header

from ..state.db import get_connection
from ..state.errors import ConsentRequired, OfferExpired
from .deps import get_clock, get_state_manager
from .schemas import HoldRequest

router = APIRouter(tags=["booking"])


@router.post("/holds", status_code=201)
def create_hold(req: HoldRequest, idempotency_key: str = Header(..., alias="Idempotency-Key")):
    clock = get_clock()
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT service_run_id, seat_plan, expires_at FROM offer WHERE offer_id=%s",
            (req.offer_id,),
        )
        row = cur.fetchone()
    conn.commit()
    if not row:
        raise OfferExpired("Offer không tồn tại", {"offer_id": req.offer_id})
    service_run_id, seat_plan_raw, expires_at = row
    if expires_at <= clock.now():
        raise OfferExpired("Offer đã hết thời gian tồn tại", {"offer_id": req.offer_id})

    seat_plan = json.loads(seat_plan_raw) if isinstance(seat_plan_raw, str) else seat_plan_raw
    # >=2 leg == ghép nhiều ghế (P5) -> bắt buộc khách xác nhận đồng ý đổi chỗ trước khi giữ ghế.
    if len(seat_plan) > 1 and not req.consent:
        raise ConsentRequired(
            "Phương án ghép nhiều ghế cần khách xác nhận đồng ý đổi chỗ trước khi giữ ghế",
            {"offer_id": req.offer_id, "so_lan_doi_cho": len(seat_plan) - 1},
        )
    legs = [(entry["seat_id"], list(range(entry["segment_from"], entry["segment_to"] + 1)))
            for entry in seat_plan]

    ssm = get_state_manager()
    result = ssm.hold_multi(service_run_id, legs, req.expected_matrix_version, idempotency_key, req.offer_id)
    return {"data": {
        "hold_id": result.hold_id,
        "status": result.status,
        "expires_at": result.expires_at.isoformat(),
        "new_matrix_version": result.new_matrix_version,
    }}


@router.post("/bookings/{hold_id}/confirm")
def confirm_booking(hold_id: str, idempotency_key: str = Header(..., alias="Idempotency-Key")):
    ssm = get_state_manager()
    result = ssm.confirm(hold_id, idempotency_key)
    return {"data": {
        "booking_id": result.booking_id,
        "status": result.status,
        "final_price_vnd": result.final_price_vnd,
        "decision_record_id": result.decision_record_id,
    }}

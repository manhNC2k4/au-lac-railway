# -*- coding: utf-8 -*-
"""POST /holds (atomic CAS) + POST /bookings/{hold_id}/confirm (idempotent, no re-price)."""
import json

from fastapi import APIRouter, Header

from ..state.db import get_connection
from ..state.errors import OfferExpired
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
    plan_entry = seat_plan[0]
    seat_id = plan_entry["seat_id"]
    segments = list(range(plan_entry["segment_from"], plan_entry["segment_to"] + 1))

    ssm = get_state_manager()
    result = ssm.hold(service_run_id, seat_id, segments, req.expected_matrix_version, idempotency_key, req.offer_id)
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

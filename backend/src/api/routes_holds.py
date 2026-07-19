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
            """SELECT o.service_run_id, o.seat_plan, o.expires_at,
                      EXISTS (
                          SELECT 1 FROM booking_candidate bc WHERE bc.offer_id=o.offer_id
                      ) AS approved_booking
                 FROM offer o WHERE o.offer_id=%s""",
            (req.offer_id,),
        )
        row = cur.fetchone()
    conn.commit()
    if not row:
        raise OfferExpired("Offer không tồn tại", {"offer_id": req.offer_id})
    service_run_id, seat_plan_raw, expires_at, approved_booking = row
    if expires_at <= clock.now():
        raise OfferExpired("Offer đã hết thời gian tồn tại", {"offer_id": req.offer_id})

    seat_plan = json.loads(seat_plan_raw) if isinstance(seat_plan_raw, str) else seat_plan_raw
    # Group candidates can contain several passengers without a seat change.
    # Consent is required only when a leg explicitly marks a seat change.
    requires_seat_change = any(entry.get("requires_seat_change", False) for entry in seat_plan)
    if requires_seat_change and not req.consent:
        raise ConsentRequired(
            "Phương án ghép nhiều ghế cần khách xác nhận đồng ý đổi chỗ trước khi giữ ghế",
            {"offer_id": req.offer_id, "so_lan_doi_cho": len(seat_plan) - 1},
        )
    legs = [(entry["seat_id"], list(range(entry["segment_from"], entry["segment_to"] + 1)))
            for entry in seat_plan]

    ssm = get_state_manager()
    result = ssm.hold_multi(
        service_run_id, legs, req.expected_matrix_version, idempotency_key,
        req.offer_id, expires_at if approved_booking else None,
    )
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE booking_candidate
                  SET status='SELECTED', updated_at=CURRENT_TIMESTAMP
                WHERE offer_id=%s RETURNING request_id, candidate_id""",
            (req.offer_id,),
        )
        candidate = cur.fetchone()
        if candidate:
            cur.execute(
                """UPDATE booking_request
                      SET status='SELECTED', selected_candidate_id=%s, hold_id=%s,
                          passenger_name=COALESCE(%s, passenger_name),
                          selected_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                    WHERE request_id=%s""",
                (candidate[1], result.hold_id, req.passenger_name, candidate[0]),
            )
    conn.commit()
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
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE booking_request
                  SET status='CONFIRMED', booking_id=%s, confirmed_at=CURRENT_TIMESTAMP,
                      updated_at=CURRENT_TIMESTAMP
                WHERE hold_id=%s""",
            (result.booking_id, hold_id),
        )
    conn.commit()
    return {"data": {
        "booking_id": result.booking_id,
        "status": result.status,
        "final_price_vnd": result.final_price_vnd,
        "decision_record_id": result.decision_record_id,
    }}

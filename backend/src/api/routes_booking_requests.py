# -*- coding: utf-8 -*-
"""Human-in-the-loop booking request workflow.

Passenger requests are priced immediately but candidates remain private until a
revenue manager approves them. The request resource is the durable state read by
both the passenger waiting screen and the admin review queue.
"""
from __future__ import annotations

import json
import uuid
from datetime import timedelta

from fastapi import APIRouter, Header, Query

from ..adapters import model_adapter
from ..forecast.topology import get_run_topology, segment_span
from ..merging import resolver
from ..state.db import get_connection
from ..state.errors import DomainError, GuardrailViolation, ResourceNotFound
from .deps import get_clock, get_state_manager, require_approver_role
from .routes_offers import create_offer
from .schemas import (BookingApprovalRequest, BookingRejectRequest,
                      BookingRequestCreate, BookingSeatSelectionRequest,
                      OfferRequest)

router = APIRouter(tags=["booking-approval"])


def _as_json(value):
    return json.loads(value) if isinstance(value, str) else value


def _request_payload(request_id: str, *, admin: bool = False) -> dict:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE booking_request br
                  SET status='EXPIRED', updated_at=CURRENT_TIMESTAMP
                WHERE br.request_id=%s AND (
                    (br.status IN ('SUBMITTED','AI_PROCESSING','PENDING_ADMIN')
                     AND br.expires_at <= CURRENT_TIMESTAMP)
                    OR (br.status='APPROVED' AND (
                        br.expires_at <= CURRENT_TIMESTAMP OR NOT EXISTS (
                            SELECT 1 FROM booking_candidate bc
                            JOIN offer o ON o.offer_id=bc.offer_id
                            WHERE bc.request_id=br.request_id
                              AND bc.status IN ('APPROVED','PRICE_OVERRIDDEN')
                              AND o.expires_at > CURRENT_TIMESTAMP
                        )
                    ))
                )""",
            (request_id,),
        )
        cur.execute(
            """SELECT request_id, service_run_id, origin_station_id, dest_station_id,
                      seat_class, quantity, priority_passenger, passenger_name, status,
                      selected_candidate_id, hold_id, booking_id, reject_code, reject_reason,
                      submitted_at, processing_started_at, ready_for_review_at, approved_at,
                      decided_by, selected_at, confirmed_at, expires_at, updated_at
                 FROM booking_request WHERE request_id=%s""",
            (request_id,),
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            raise ResourceNotFound("Không tìm thấy yêu cầu đặt vé", {"request_id": request_id})

        status = row[8]
        visible_statuses = ("APPROVED", "PRICE_OVERRIDDEN", "SELECTED")
        sql = (
            """SELECT bc.candidate_id, bc.offer_id, bc.decision_record_id, bc.rank,
                      bc.ai_recommended, bc.status, bc.seat_plan, bc.pricing,
                      bc.explanation, bc.approved_price_vnd, bc.admin_note,
                      bc.approved_by, bc.approved_at, o.matrix_version,
                      o.forecast_version, o.policy_version, o.decision, o.expires_at
                 FROM booking_candidate bc
                 JOIN offer o ON o.offer_id=bc.offer_id
                WHERE bc.request_id=%s"""
        )
        params: list = [request_id]
        if not admin:
            sql += " AND bc.status = ANY(%s)"
            params.append(list(visible_statuses))
        sql += " ORDER BY bc.ai_recommended DESC, bc.rank"
        cur.execute(sql, params)
        candidate_rows = cur.fetchall()
    conn.commit()

    candidates = []
    for candidate in candidate_rows:
        seat_plan = _as_json(candidate[6]) or []
        candidates.append({
            "candidate_id": candidate[0],
            "offer_id": candidate[1],
            "decision_record_id": candidate[2],
            "rank": candidate[3],
            "ai_recommended": candidate[4],
            "status": candidate[5],
            "seat_plan": seat_plan,
            "pricing": _as_json(candidate[7]) or {},
            "explanation": candidate[8],
            "approved_price_vnd": candidate[9],
            "admin_note": candidate[10] if admin else None,
            "approved_by": candidate[11] if admin else None,
            "approved_at": candidate[12].isoformat() if candidate[12] else None,
            "matrix_version": candidate[13],
            "forecast_version": candidate[14],
            "policy_version": candidate[15],
            "decision": candidate[16],
            "expires_at": candidate[17].isoformat(),
            "requires_customer_consent": any(item.get("requires_seat_change", False) for item in seat_plan),
        })

    return {
        "request_id": row[0],
        "service_run_id": row[1],
        "origin_station_id": row[2],
        "dest_station_id": row[3],
        "seat_class": row[4],
        "quantity": row[5],
        "priority_passenger": row[6],
        "passenger_name": row[7],
        "status": status,
        "selected_candidate_id": row[9],
        "hold_id": row[10],
        "booking_id": row[11],
        "reject_code": row[12],
        "reject_reason": row[13],
        "submitted_at": row[14].isoformat(),
        "processing_started_at": row[15].isoformat() if row[15] else None,
        "ready_for_review_at": row[16].isoformat() if row[16] else None,
        "approved_at": row[17].isoformat() if row[17] else None,
        "decided_by": row[18] if admin else None,
        "selected_at": row[19].isoformat() if row[19] else None,
        "confirmed_at": row[20].isoformat() if row[20] else None,
        "expires_at": row[21].isoformat(),
        "updated_at": row[22].isoformat(),
        "candidates": candidates,
    }


def _reject_processing(request_id: str, exc: DomainError) -> None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE booking_request
                  SET status='REJECTED', reject_code=%s, reject_reason=%s,
                      updated_at=CURRENT_TIMESTAMP
                WHERE request_id=%s""",
            (exc.error_code, exc.message, request_id),
        )
    conn.commit()


@router.post("/booking-requests", status_code=201)
def submit_booking_request(body: BookingRequestCreate):
    request_id = f"br_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT 1 FROM service_run
                WHERE service_run_id=%s AND status='ACTIVE' AND service_date >= CURRENT_DATE""",
            (body.service_run_id,),
        )
        if cur.fetchone() is None:
            conn.rollback()
            raise ResourceNotFound(
                "Chuyến không tồn tại, đã qua ngày chạy hoặc chưa mở bán",
                {"service_run_id": body.service_run_id},
            )
        cur.execute(
            """INSERT INTO booking_request
               (request_id, service_run_id, origin_station_id, dest_station_id,
                seat_class, quantity, priority_passenger, passenger_name, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'SUBMITTED')""",
            (request_id, body.service_run_id, body.origin_station_id,
             body.dest_station_id, body.seat_class, body.quantity,
             body.priority_passenger, body.passenger_name),
        )
        cur.execute(
            """UPDATE booking_request SET status='AI_PROCESSING',
                      processing_started_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                WHERE request_id=%s""",
            (request_id,),
        )
    conn.commit()

    offer_request = OfferRequest(**body.model_dump(exclude={"passenger_name"}))
    try:
        offer_data = create_offer(offer_request)["data"]
    except DomainError as exc:
        _reject_processing(request_id, exc)
        return {"data": _request_payload(request_id)}

    quantity = body.quantity
    topology = get_run_topology(body.service_run_id)
    seg_from, seg_to = segment_span(topology, body.origin_station_id, body.dest_station_id)
    seatmap = get_state_manager().get_seatmap(body.service_run_id, body.seat_class)
    matrix, seat_ids = model_adapter.seatmap_to_matrix(seatmap, topology["n_segments"])
    options = resolver.resolve_same_seat_options(
        matrix, seat_ids, seg_from, seg_to,
        priority_passenger=body.priority_passenger,
    )

    # Rolling demo runs always have continuous options. Keep the original merged
    # offer as a single candidate for the legacy fixed scenario.
    if options:
        groups = [options[i:i + quantity] for i in range(0, min(len(options), quantity * 3), quantity)]
        groups = [group for group in groups if len(group) == quantity][:3]
        if not groups:
            exc = ResourceNotFound(
                "Không còn đủ ghế cho số hành khách đã chọn",
                {"quantity": quantity, "available": len(options)},
            )
            _reject_processing(request_id, exc)
            return {"data": _request_payload(request_id)}
        plans = [[{
            "seat_id": item.seat_id,
            "segment_from": item.segment_from,
            "segment_to": item.segment_to,
            "reused_gap": item.reused_gap,
            "requires_seat_change": False,
            "passenger_no": passenger_no + 1,
        } for passenger_no, item in enumerate(group)] for group in groups]
    elif quantity == 1:
        plans = [offer_data["seat_plan"]]
    else:
        exc = ResourceNotFound(
            "Không còn đủ ghế liên tục cho nhóm hành khách",
            {"quantity": quantity},
        )
        _reject_processing(request_id, exc)
        return {"data": _request_payload(request_id)}

    unit_pricing = offer_data["pricing"]
    pricing = {
        **unit_pricing,
        "unit_price_vnd": unit_pricing["gia_cuoi_vnd"],
        "gia_goc_vnd": unit_pricing["gia_goc_vnd"] * quantity,
        "gia_niem_yet_vnd": unit_pricing["gia_niem_yet_vnd"] * quantity,
        "gia_cuoi_vnd": unit_pricing["gia_cuoi_vnd"] * quantity,
        "quantity": quantity,
    }
    total_price = pricing["gia_cuoi_vnd"]
    base_offer_id = offer_data["offer_id"]
    decision_record_id = offer_data["decision_record_id"]
    now = get_clock().now()

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE offer SET seat_plan=%s, final_price_vnd=%s WHERE offer_id=%s""",
            (json.dumps(plans[0], ensure_ascii=False), total_price, base_offer_id),
        )
        if quantity > 1:
            cur.execute(
                """UPDATE decision_record
                      SET base_fare_vnd=base_fare_vnd * %s,
                          ai_suggested_price_vnd=ai_suggested_price_vnd * %s,
                          final_price_vnd=final_price_vnd * %s,
                          bid_price_total_vnd=bid_price_total_vnd * %s
                    WHERE decision_id=%s""",
                (quantity, quantity, quantity, quantity, decision_record_id),
            )

        for index, plan in enumerate(plans):
            offer_id = base_offer_id
            if index > 0:
                offer_id = f"offer_{uuid.uuid4().hex[:12]}"
                cur.execute(
                    """INSERT INTO offer
                       (offer_id, service_run_id, matrix_version, forecast_version,
                        policy_version, decision, seat_plan, final_price_vnd, expires_at,
                        origin_station_id, dest_station_id, seat_class)
                       SELECT %s, service_run_id, matrix_version, forecast_version,
                              policy_version, decision, %s, %s, expires_at,
                              origin_station_id, dest_station_id, seat_class
                         FROM offer WHERE offer_id=%s""",
                    (offer_id, json.dumps(plan, ensure_ascii=False), total_price, base_offer_id),
                )
            candidate_id = f"bc_{uuid.uuid4().hex[:12]}"
            cur.execute(
                """INSERT INTO booking_candidate
                   (candidate_id, request_id, offer_id, decision_record_id, rank,
                    ai_recommended, status, seat_plan, pricing, explanation)
                   VALUES (%s,%s,%s,%s,%s,%s,'AI_SUGGESTED',%s,%s,%s)""",
                (candidate_id, request_id, offer_id, decision_record_id, index + 1,
                 index == 0, json.dumps(plan, ensure_ascii=False),
                 json.dumps(pricing, ensure_ascii=False), offer_data["explanation"]),
            )
        cur.execute(
            """UPDATE booking_request
                  SET status='PENDING_ADMIN', ready_for_review_at=%s,
                      updated_at=%s WHERE request_id=%s""",
            (now, now, request_id),
        )
    conn.commit()
    return {"data": _request_payload(request_id)}


@router.get("/booking-requests/{request_id}")
def get_booking_request(request_id: str):
    return {"data": _request_payload(request_id)}


@router.get("/booking-requests/{request_id}/seat-layout")
def get_booking_seat_layout(request_id: str):
    request = _request_payload(request_id)
    if request["status"] not in ("APPROVED", "SELECTED"):
        raise GuardrailViolation(
            "Sơ đồ ghế chỉ mở sau khi phương án giá được duyệt",
            {"status": request["status"]},
        )

    topology = get_run_topology(request["service_run_id"])
    seg_from, seg_to = segment_span(
        topology, request["origin_station_id"], request["dest_station_id"]
    )
    expected_segments = seg_to - seg_from + 1
    recommended_ids = {
        item["seat_id"]
        for candidate in request["candidates"] if candidate["ai_recommended"]
        for item in candidate["seat_plan"]
    }
    approved_ids = {
        item["seat_id"]
        for candidate in request["candidates"]
        for item in candidate["seat_plan"]
    }

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT sr.train_id FROM service_run sr WHERE sr.service_run_id=%s""",
            (request["service_run_id"],),
        )
        train_row = cur.fetchone()
        if train_row is None:
            conn.rollback()
            raise ResourceNotFound("Không tìm thấy đoàn tàu của chuyến", {})
        train_id = train_row[0]
        cur.execute(
            """SELECT cl.coach_number, cl.coach_label, cl.seat_class,
                      cl.layout_type, cl.capacity, cl.data_source,
                      sl.seat_index, sl.seat_number, sl.row_number,
                      sl.column_code, sl.position_code, sl.compartment_number,
                      sl.berth_level, sl.is_accessible,
                      MIN(sss.seat_id) AS seat_id,
                      COUNT(sss.segment_id) AS segment_count,
                      BOOL_AND(sss.status='FREE') AS all_free,
                      BOOL_OR(sss.status='SOLD') AS any_sold,
                      BOOL_OR(sss.status='HELD') AS any_held
                 FROM train_coach_layout cl
                 LEFT JOIN train_seat_layout sl
                   ON sl.train_id=cl.train_id AND sl.coach_number=cl.coach_number
                 LEFT JOIN seat_segment_state sss
                   ON sss.service_run_id=%s
                  AND sss.seat_class=sl.seat_class
                  AND sss.seat_index=sl.seat_index
                  AND sss.segment_id BETWEEN %s AND %s
                WHERE cl.train_id=%s
                GROUP BY cl.coach_number, cl.coach_label, cl.seat_class,
                         cl.layout_type, cl.capacity, cl.display_order,
                         cl.data_source, sl.seat_index, sl.seat_number,
                         sl.row_number, sl.column_code, sl.position_code,
                         sl.compartment_number, sl.berth_level, sl.is_accessible
                ORDER BY cl.display_order, sl.seat_number""",
            (request["service_run_id"], seg_from, seg_to, train_id),
        )
        rows = cur.fetchall()
    conn.commit()

    coaches: dict[int, dict] = {}
    for row in rows:
        coach = coaches.setdefault(row[0], {
            "coach_number": row[0], "coach_label": row[1],
            "seat_class": row[2], "layout_type": row[3],
            "capacity": row[4], "data_source": row[5], "seats": [],
        })
        if row[6] is None:
            continue
        seat_id = row[14]
        if row[2] != request["seat_class"] or row[15] != expected_segments:
            state = "UNAVAILABLE"
        elif row[17]:
            state = "BOOKED"
        elif row[18] or not row[16]:
            state = "UNAVAILABLE"
        else:
            state = "AVAILABLE"
        coach["seats"].append({
            "seat_id": seat_id,
            "seat_index": row[6], "seat_number": row[7],
            "row_number": row[8], "column_code": row[9],
            "position_code": row[10], "compartment_number": row[11],
            "berth_level": row[12], "is_accessible": row[13],
            "state": state,
            "ai_recommended": seat_id in recommended_ids,
            "approved_option": seat_id in approved_ids,
        })

    return {"data": {
        "request_id": request_id,
        "train_id": train_id,
        "seat_class": request["seat_class"],
        "quantity": request["quantity"],
        "segment_from": seg_from, "segment_to": seg_to,
        "layout_source": "DERIVED_UI_LAYOUT_V1",
        "coaches": list(coaches.values()),
    }}


@router.post("/booking-requests/{request_id}/seat-selection")
def select_booking_seats(request_id: str, body: BookingSeatSelectionRequest):
    request = _request_payload(request_id)
    if request["status"] != "APPROVED":
        raise GuardrailViolation(
            "Chỉ chọn được ghế khi yêu cầu đã được duyệt",
            {"status": request["status"]},
        )
    seat_ids = list(dict.fromkeys(body.seat_ids))
    if len(seat_ids) != request["quantity"]:
        raise GuardrailViolation(
            "Số ghế chọn phải bằng số hành khách",
            {"required": request["quantity"], "selected": len(seat_ids)},
        )
    candidate = next(
        (item for item in request["candidates"] if item["candidate_id"] == body.candidate_id),
        None,
    )
    if candidate is None:
        raise ResourceNotFound("Phương án không thuộc yêu cầu đã duyệt", {})

    topology = get_run_topology(request["service_run_id"])
    seg_from, seg_to = segment_span(
        topology, request["origin_station_id"], request["dest_station_id"]
    )
    expected_segments = seg_to - seg_from + 1
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT sss.seat_id, tsl.seat_class,
                          COUNT(*) AS segment_count,
                          BOOL_AND(sss.status='FREE') AS all_free
                     FROM seat_segment_state sss
                     JOIN service_run sr ON sr.service_run_id=sss.service_run_id
                     JOIN train_seat_layout tsl
                       ON tsl.train_id=sr.train_id
                      AND tsl.seat_class=sss.seat_class
                      AND tsl.seat_index=sss.seat_index
                    WHERE sss.service_run_id=%s AND sss.seat_id=ANY(%s)
                      AND sss.segment_id BETWEEN %s AND %s
                    GROUP BY sss.seat_id, tsl.seat_class""",
                (request["service_run_id"], seat_ids, seg_from, seg_to),
            )
            availability = {row[0]: row[1:] for row in cur.fetchall()}
            invalid = [seat_id for seat_id in seat_ids if (
                seat_id not in availability
                or availability[seat_id][0] != request["seat_class"]
                or availability[seat_id][1] != expected_segments
                or not availability[seat_id][2]
            )]
            if invalid:
                raise GuardrailViolation(
                    "Một hoặc nhiều ghế vừa không còn khả dụng",
                    {"seat_ids": invalid},
                )

            plan = [{
                "seat_id": seat_id,
                "segment_from": seg_from,
                "segment_to": seg_to,
                "reused_gap": False,
                "requires_seat_change": False,
                "passenger_no": index + 1,
            } for index, seat_id in enumerate(seat_ids)]
            new_offer_id = f"offer_{uuid.uuid4().hex[:12]}"
            cur.execute(
                """INSERT INTO offer
                   (offer_id, service_run_id, matrix_version, forecast_version,
                    policy_version, decision, seat_plan, final_price_vnd,
                    expires_at, origin_station_id, dest_station_id, seat_class)
                   SELECT %s, service_run_id, matrix_version, forecast_version,
                          policy_version, decision, %s, final_price_vnd,
                          expires_at, origin_station_id, dest_station_id, seat_class
                     FROM offer WHERE offer_id=%s""",
                (new_offer_id, json.dumps(plan, ensure_ascii=False), candidate["offer_id"]),
            )
            if cur.rowcount != 1:
                raise ResourceNotFound("Offer đã duyệt không còn tồn tại", {})
            cur.execute(
                """UPDATE booking_candidate
                      SET offer_id=%s, seat_plan=%s, updated_at=CURRENT_TIMESTAMP
                    WHERE candidate_id=%s AND request_id=%s""",
                (new_offer_id, json.dumps(plan, ensure_ascii=False),
                 body.candidate_id, request_id),
            )
            cur.execute(
                """INSERT INTO audit_log
                   (actor, action, entity_type, entity_id, new_value)
                   VALUES ('passenger','SELECT_SEATS','booking_request',%s,%s)""",
                (request_id, json.dumps({
                    "candidate_id": body.candidate_id, "seat_ids": seat_ids,
                }, ensure_ascii=False)),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"data": _request_payload(request_id)}


@router.delete("/booking-requests/{request_id}")
def cancel_booking_request(request_id: str):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE booking_request
                  SET status='REJECTED', reject_code='CUSTOMER_CANCELLED',
                      reject_reason='Khách hàng đã huỷ yêu cầu', updated_at=CURRENT_TIMESTAMP
                WHERE request_id=%s AND status IN ('SUBMITTED','AI_PROCESSING','PENDING_ADMIN','APPROVED')
                RETURNING request_id""",
            (request_id,),
        )
        changed = cur.fetchone()
    conn.commit()
    if changed is None:
        current = _request_payload(request_id)
        if current["status"] not in ("REJECTED", "EXPIRED"):
            raise GuardrailViolation("Không thể huỷ yêu cầu ở trạng thái hiện tại", {"status": current["status"]})
    return {"data": _request_payload(request_id)}


@router.get("/admin/booking-requests")
def list_admin_booking_requests(
    status: str = Query(default="PENDING_ADMIN"),
    service_run_id: str | None = None,
    x_actor_role: str = Header(..., alias="X-Actor-Role"),
):
    require_approver_role(x_actor_role)
    conn = get_connection()
    with conn.cursor() as cur:
        sql = (
            """SELECT br.request_id
                 FROM booking_request br
                WHERE br.status=%s"""
        )
        params: list = [status]
        if service_run_id:
            sql += " AND br.service_run_id=%s"
            params.append(service_run_id)
        sql += " ORDER BY br.submitted_at LIMIT 200"
        cur.execute(sql, params)
        ids = [row[0] for row in cur.fetchall()]
    conn.commit()
    requests = [_request_payload(request_id, admin=True) for request_id in ids]
    return {"data": {"requests": requests, "total": len(requests)}}


@router.get("/admin/booking-requests/{request_id}")
def get_admin_booking_request(
    request_id: str,
    x_actor_role: str = Header(..., alias="X-Actor-Role"),
):
    require_approver_role(x_actor_role)
    return {"data": _request_payload(request_id, admin=True)}


@router.post("/admin/booking-requests/{request_id}/approve")
def approve_booking_request(
    request_id: str,
    body: BookingApprovalRequest,
    x_actor_role: str = Header(..., alias="X-Actor-Role"),
):
    require_approver_role(x_actor_role)
    selected = {item.candidate_id: item for item in body.approved_candidates}
    if len(selected) != len(body.approved_candidates):
        raise GuardrailViolation("Danh sách duyệt chứa candidate trùng nhau", {})

    now = get_clock().now()
    offer_expires_at = now + timedelta(minutes=15)
    request_expires_at = now + timedelta(minutes=15)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status, service_run_id, origin_station_id, dest_station_id,
                          seat_class, quantity
                     FROM booking_request WHERE request_id=%s FOR UPDATE""",
                (request_id,),
            )
            request_row = cur.fetchone()
            if request_row is None:
                raise ResourceNotFound("Không tìm thấy yêu cầu đặt vé", {"request_id": request_id})
            if request_row[0] == "APPROVED":
                conn.rollback()
                return {"data": _request_payload(request_id, admin=True)}
            if request_row[0] != "PENDING_ADMIN":
                raise GuardrailViolation("Chỉ duyệt được yêu cầu đang chờ admin", {"status": request_row[0]})

            cur.execute(
                """SELECT bc.candidate_id, bc.offer_id, bc.pricing
                     FROM booking_candidate bc WHERE bc.request_id=%s FOR UPDATE""",
                (request_id,),
            )
            candidate_rows = cur.fetchall()
            known_ids = {row[0] for row in candidate_rows}
            missing = sorted(set(selected) - known_ids)
            if missing:
                raise ResourceNotFound("Candidate không thuộc yêu cầu", {"candidate_ids": missing})

            cur.execute(
                """SELECT fp.base_fare_vnd, pp.floor_ratio, pp.ceiling_ratio
                     FROM fare_product fp
                     CROSS JOIN LATERAL (
                         SELECT floor_ratio, ceiling_ratio FROM pricing_policy
                         WHERE is_active=TRUE ORDER BY policy_id DESC LIMIT 1
                     ) pp
                    WHERE fp.service_run_id=%s AND fp.origin_station_id=%s
                      AND fp.dest_station_id=%s AND fp.seat_class=%s
                    ORDER BY fp.version DESC LIMIT 1""",
                (request_row[1], request_row[2], request_row[3], request_row[4]),
            )
            policy_row = cur.fetchone()
            if policy_row is None:
                raise GuardrailViolation("Thiếu fare hoặc pricing policy để duyệt giá", {})
            base_fare, floor_ratio, ceiling_ratio = policy_row
            lower = round(int(base_fare) * request_row[5] * float(floor_ratio))
            upper = round(int(base_fare) * request_row[5] * float(ceiling_ratio))

            for candidate_id, offer_id, pricing_raw in candidate_rows:
                approval = selected.get(candidate_id)
                if approval is None:
                    cur.execute(
                        "UPDATE booking_candidate SET status='REJECTED', updated_at=%s WHERE candidate_id=%s",
                        (now, candidate_id),
                    )
                    continue
                pricing = _as_json(pricing_raw) or {}
                price = approval.override_price_vnd or int(pricing["gia_cuoi_vnd"])
                if not lower <= price <= upper:
                    raise GuardrailViolation(
                        "Giá duyệt nằm ngoài guardrail",
                        {"candidate_id": candidate_id, "floor": lower, "ceiling": upper, "requested": price},
                    )
                overridden = approval.override_price_vnd is not None and price != int(pricing["gia_cuoi_vnd"])
                pricing["gia_cuoi_vnd"] = price
                candidate_status = "PRICE_OVERRIDDEN" if overridden else "APPROVED"
                cur.execute(
                    """UPDATE booking_candidate
                          SET status=%s, pricing=%s, approved_price_vnd=%s, admin_note=%s,
                              approved_by=%s, approved_at=%s, updated_at=%s
                        WHERE candidate_id=%s""",
                    (candidate_status, json.dumps(pricing, ensure_ascii=False), price,
                     approval.reason or body.note, body.decided_by, now, now, candidate_id),
                )
                cur.execute(
                    "UPDATE offer SET final_price_vnd=%s, expires_at=%s WHERE offer_id=%s",
                    (price, offer_expires_at, offer_id),
                )

            cur.execute(
                """UPDATE booking_request
                      SET status='APPROVED', approved_at=%s, decided_by=%s,
                          expires_at=%s, updated_at=%s WHERE request_id=%s""",
                (now, body.decided_by, request_expires_at, now, request_id),
            )
            cur.execute(
                """INSERT INTO audit_log
                   (actor, action, entity_type, entity_id, new_value)
                   VALUES (%s,'APPROVE','booking_request',%s,%s)""",
                (body.decided_by, request_id, json.dumps({
                    "approved_candidate_ids": list(selected), "note": body.note,
                }, ensure_ascii=False)),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"data": _request_payload(request_id, admin=True)}


@router.post("/admin/booking-requests/{request_id}/reject")
def reject_booking_request(
    request_id: str,
    body: BookingRejectRequest,
    x_actor_role: str = Header(..., alias="X-Actor-Role"),
):
    require_approver_role(x_actor_role)
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE booking_request
                  SET status='REJECTED', reject_code='ADMIN_REJECTED', reject_reason=%s,
                      decided_by=%s, updated_at=CURRENT_TIMESTAMP
                WHERE request_id=%s AND status='PENDING_ADMIN' RETURNING request_id""",
            (body.reason, body.decided_by, request_id),
        )
        changed = cur.fetchone()
        if changed:
            cur.execute(
                """UPDATE booking_candidate SET status='REJECTED', updated_at=CURRENT_TIMESTAMP
                    WHERE request_id=%s AND status='AI_SUGGESTED'""",
                (request_id,),
            )
            cur.execute(
                """INSERT INTO audit_log
                   (actor, action, entity_type, entity_id, new_value)
                   VALUES (%s,'REJECT','booking_request',%s,%s)""",
                (body.decided_by, request_id,
                 json.dumps({"reason": body.reason}, ensure_ascii=False)),
            )
    conn.commit()
    if changed is None:
        current = _request_payload(request_id, admin=True)
        if current["status"] != "REJECTED":
            raise GuardrailViolation("Chỉ từ chối được yêu cầu đang chờ admin", {"status": current["status"]})
    return {"data": _request_payload(request_id, admin=True)}

# -*- coding: utf-8 -*-
"""P7.3 (C5 hàng chờ thông minh) — POST /waitlist (khách chủ động vào chờ sau
NO_SAME_SEAT_OPTION), GET /waitlist (xem hàng đợi), POST /waitlist/match (ops trigger
khớp lại sau khi có hold hết hạn/hủy vé — xem ghi chú `ponytail` trong waitlist/service.py
về việc không có worker nền trong demo này)."""
from fastapi import APIRouter

from ..state.db import get_connection
from ..waitlist import service as waitlist_service
from .deps import get_pricer
from .schemas import WaitlistAddRequest

router = APIRouter(tags=["waitlist"])


@router.post("/waitlist", status_code=201)
def waitlist_add(req: WaitlistAddRequest):
    conn = get_connection()
    result = waitlist_service.add(
        conn, get_pricer(), req.service_run_id, req.origin_station_id, req.dest_station_id,
        req.seat_class, req.u, req.quantity, req.priority_passenger, req.csxh_doi_tuong,
    )
    return {"data": result}


@router.get("/waitlist")
def waitlist_list(service_run_id: str):
    conn = get_connection()
    return {"data": {"pending": waitlist_service.pending(conn, service_run_id)}}


@router.post("/waitlist/match")
def waitlist_match(service_run_id: str):
    conn = get_connection()
    return {"data": waitlist_service.match(conn, service_run_id)}

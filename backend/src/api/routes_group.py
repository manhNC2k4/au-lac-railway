# -*- coding: utf-8 -*-
"""POST /group/quote (P7.4, C4 xếp nhóm) — đề xuất ghế cùng toa/khoang cho nhóm/gia
đình qua `app.group_seating.plan_group` (CP-SAT, fallback greedy). Thuần đề xuất:
không giữ ghế — khách đồng ý thì gọi `/offers` + `/holds` như luồng bình thường cho
từng ghế trong `assignments` (P5 hold_multi đã hỗ trợ CAS nhiều ghế cùng lúc)."""
from fastapi import APIRouter

from ..audit import log as audit_log
from ..group.service import quote_group
from ..state.db import get_connection
from ..state.errors import NoSameSeatOption
from .deps import get_state_manager
from .schemas import GroupQuoteRequest

router = APIRouter(tags=["group"])


@router.post("/group/quote")
def group_quote(req: GroupQuoteRequest):
    ssm = get_state_manager()
    result = quote_group(ssm, req.service_run_id, req.origin_station_id,
                         req.dest_station_id, req.seat_class, req.n_khach)
    conn = get_connection()
    audit_log.persist(conn, result["_log"], req.service_run_id)
    if not result["plan"]["kha_thi"]:
        raise NoSameSeatOption(result["plan"]["ghi_chu"], {
            "origin_station_id": req.origin_station_id, "dest_station_id": req.dest_station_id,
            "n_khach": req.n_khach})
    return {"data": result["plan"]}

# -*- coding: utf-8 -*-
"""Đề xuất giá vé theo chặng — GET danh sách (xếp theo doanh thu tăng thêm giảm dần) +
POST duyệt/từ chối (role revenue_manager/admin qua `X-Actor-Role`). ACCEPT áp giá vào
fare_product của đoạn. AI ĐỀ XUẤT, nhân viên QUYẾT — không auto-quyết."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from ..pricing import suggestions
from ..state.db import get_connection
from .deps import get_clock, get_state_manager, require_approver_role
from .schemas import PriceDecisionRequest

router = APIRouter(tags=["pricing"])


@router.get("/pricing/suggestions")
def list_suggestions(service_run_id: str):
    conn = get_connection()
    data = suggestions.compute(conn, get_state_manager(), get_clock(), service_run_id)
    return {"data": data}


@router.post("/pricing/suggestions/decide")
def decide_suggestion(body: PriceDecisionRequest,
                      x_actor_role: str = Header(..., alias="X-Actor-Role")):
    require_approver_role(x_actor_role)
    conn = get_connection()
    result = suggestions.decide(conn, get_state_manager(), get_clock(),
                                body.service_run_id, body.segment_id, body.decision, body.decided_by)
    if result is None:
        return JSONResponse(status_code=404, content={
            "error_code": "RESOURCE_NOT_FOUND", "message": "Không tìm thấy đoạn để duyệt giá",
            "details": {"segment_id": body.segment_id}})
    return {"data": result}

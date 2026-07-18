# -*- coding: utf-8 -*-
"""P7.2 (C2 tái phân bổ + phê duyệt + rollback) — POST /allocation/refresh (đề xuất
hạn mức mới), GET /allocation/{version}, POST /allocation/{version}/approve|reject|rollback
(role revenue_manager/admin qua header `X-Actor-Role`)."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from ..allocation import reallocation
from ..state.db import get_connection
from .deps import require_approver_role
from .schemas import AllocationDecisionRequest

router = APIRouter(tags=["allocation"])


def _not_found(version: int) -> JSONResponse:
    return JSONResponse(status_code=404, content={
        "error_code": "RESOURCE_NOT_FOUND", "message": "Không tìm thấy bản hạn mức",
        "details": {"version": version},
    })


@router.post("/allocation/refresh", status_code=201)
def allocation_refresh(service_run_id: str):
    conn = get_connection()
    return {"data": reallocation.propose(conn, service_run_id)}


@router.get("/allocation/{version}")
def allocation_get(version: int, service_run_id: str):
    conn = get_connection()
    v = reallocation.get_version(conn, service_run_id, version)
    if v is None:
        return _not_found(version)
    return {"data": v}


@router.post("/allocation/{version}/approve")
def allocation_approve(version: int, service_run_id: str, body: AllocationDecisionRequest,
                       x_actor_role: str = Header(..., alias="X-Actor-Role")):
    require_approver_role(x_actor_role)
    conn = get_connection()
    v = reallocation.approve(conn, service_run_id, version, body.decided_by)
    if v is None:
        return _not_found(version)
    return {"data": v}


@router.post("/allocation/{version}/reject")
def allocation_reject(version: int, service_run_id: str, body: AllocationDecisionRequest,
                      x_actor_role: str = Header(..., alias="X-Actor-Role")):
    require_approver_role(x_actor_role)
    conn = get_connection()
    v = reallocation.reject(conn, service_run_id, version, body.decided_by)
    if v is None:
        return _not_found(version)
    return {"data": v}


@router.post("/allocation/{version}/rollback")
def allocation_rollback(version: int, service_run_id: str, body: AllocationDecisionRequest,
                        x_actor_role: str = Header(..., alias="X-Actor-Role")):
    require_approver_role(x_actor_role)
    conn = get_connection()
    v = reallocation.rollback(conn, service_run_id, version, body.decided_by)
    if v is None:
        return _not_found(version)
    return {"data": v}

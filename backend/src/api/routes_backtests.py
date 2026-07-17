# -*- coding: utf-8 -*-
"""POST /backtests + GET /backtests/{report_id} + GET /decisions/{decision_id}.

Backtest chạy engine BE2 trên 5 event stream ĐÃ COMMIT (seed/backtest/*.jsonl),
với giá thật T5 (baseline = niêm yết, Âu Lạc = PricingEngine). ~2000 request tổng,
chạy đồng bộ trong request là đủ nhanh — trả 202 + report_id, report lấy qua GET.
"""
import json
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..backtest import engine
from ..state.db import get_connection

router = APIRouter(tags=["backtest"])

# ponytail: report giữ in-memory theo process — demo single-instance; chuyển sang
# bảng Postgres nếu cần sống sót qua restart.
_REPORTS: dict[str, dict] = {}


def _not_found(resource: str, rid: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={
        "error_code": "RESOURCE_NOT_FOUND", "message": f"Không tìm thấy {resource}",
        "details": {"id": rid},
    })


@router.post("/backtests", status_code=202)
def create_backtest(body: dict):
    seeds = [int(s) for s in body.get("seeds", [])] or None
    baseline_fn, aulac_fn = engine.make_priced_fare_fns()
    report = engine.run_backtest(engine.load_all_events(seeds), baseline_fn, aulac_fn)
    report_id = f"bt_{uuid.uuid4().hex[:12]}"
    _REPORTS[report_id] = report
    return {"message": "Backtest started", "data": {"report_id": report_id}}


@router.get("/backtests/{report_id}")
def get_backtest(report_id: str):
    report = _REPORTS.get(report_id)
    if report is None:
        return _not_found("backtest report", report_id)
    return {"data": {
        "status": "COMPLETED",
        "seeds_run": report["seeds_run"],
        "failed_seeds": report["failed_seeds"],
        "baseline_metrics": report["baseline_metrics"],
        "ai_metrics": report["aulac_metrics"],   # tên field theo openapi.yaml
        "raw": report["raw"],
        "checksum": report["checksum"],
    }}


@router.get("/decisions/{decision_id}")
def get_decision(decision_id: str):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT decision_id, input_hash, versions, result, base_fare_vnd,
                      ai_suggested_price_vnd, final_price_vnd, bid_price_total_vnd,
                      bid_price_breakdown, violations, audit_timeline,
                      explanation_code, actor, created_at
               FROM decision_record WHERE decision_id=%s""",
            (decision_id,),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        return _not_found("decision", decision_id)

    def _jsonb(v):
        return json.loads(v) if isinstance(v, str) else v

    return {"data": {
        "decision_id": row[0],
        "input_hash": row[1],
        "versions": _jsonb(row[2]),
        "action": row[3],
        "base_fare": row[4],
        "ai_suggested_price": row[5],
        "final_price": row[6],
        "bid_price_total": row[7],
        "bid_price_breakdown": _jsonb(row[8]),
        "violations": _jsonb(row[9]) or [],
        "audit_timeline": _jsonb(row[10]),
        "explanation_code": row[11],
        "actor": row[12],
        "created_at": row[13].isoformat(),
    }}

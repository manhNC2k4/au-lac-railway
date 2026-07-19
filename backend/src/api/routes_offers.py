# -*- coding: utf-8 -*-
"""POST /offers — pipeline thật (Master §8): snapshot → resolver BE3 → F0 →
PricingEngine (YAML rules + guardrail + CSXH max-last) → so Σbid BE2 → Offer
immutable + DecisionRecord append-only. KHÔNG giữ ghế (đó là việc của /holds).

Tích hợp H10-H14: thay logic rút gọn của phiên solo BE1 bằng 3 module BE3
(`merging.resolver`, `pricing.engine`, `offer.service`) + bid DLP thật qua
`allocation.cache` (P2 Bước4, live-import `app.bt3_allocation`). Route/response shape
GIỮ NGUYÊN theo openapi.yaml.
"""
import json
import os
from datetime import date

import numpy as np
from fastapi import APIRouter, Header

from ..adapters import model_adapter
from ..allocation import cache as allocation_cache
from ..forecast import network
from ..forecast.runtime import ensure_model_forecast
from ..forecast.topology import distance_km, get_run_topology, segment_span
from ..merging import resolver
from ..offer import override as override_service
from ..offer.service import OfferService
from ..pricing.context import PricingContext
from ..pricing.engine import PolicyUnavailableError, PricingEngine
from ..state.db import get_connection
from ..state.errors import AllocationRejected, NoSameSeatOption, PolicyUnavailable
from .deps import SEED_DIR, get_clock, get_pricer, get_state_manager, require_approver_role
from .schemas import OfferRequest, OverrideRequest

router = APIRouter(tags=["booking"])
MIN_SEAT_CHANGE_DWELL_MIN = float(os.environ.get(
    "MIN_SEAT_CHANGE_DWELL_MIN", str(resolver.DEFAULT_MIN_DWELL_MIN),
))

# Scenario metadata provides pricing mode only. service_date is read from the
# selected run so rolling/future demo data gets the correct lead time.
_SCENARIO = json.loads((SEED_DIR / "scenario.json").read_text(encoding="utf-8"))
# csxh table sống ở seed (bảng pricing_policy V1 không có cột csxh — không sửa migration P0).
_SEED_POLICY = json.loads((SEED_DIR / "pricing_policy.json").read_text(encoding="utf-8"))

PEAK_SUMMER = (date(2026, 5, 15), date(2026, 8, 16))  # nguồn: spec (Master §1.1 — cao điểm hè 2026)


def seg_range(origin: str, dest: str, service_run_id: str | None = None) -> tuple[int, int]:
    if service_run_id:
        return segment_span(get_run_topology(service_run_id), origin, dest)
    ids = [station["id"] for station in network.STATIONS]
    if origin not in ids or dest not in ids:
        raise NoSameSeatOption("Ga ngoài tuyến tàu", {"origin": origin, "dest": dest})
    i, j = ids.index(origin), ids.index(dest)
    if i >= j:
        raise NoSameSeatOption("origin phải trước dest theo lý trình", {"origin": origin, "dest": dest})
    return i + 1, j


def _matrix_from_seatmap(seatmap: dict, n_segments: int) -> tuple[np.ndarray, list[str]]:
    # Chuyển hoá đi qua adapter duy nhất (§3.4) — không convert tay trong route.
    return model_adapter.seatmap_to_matrix(seatmap, n_segments)


def _latest_forecast(cur, service_run_id: str, seat_class: str) -> tuple[dict[int, float], int]:
    """Map segment_id -> forecast_remaining của version mới nhất. Hàng insert theo
    thứ tự segment (reset + refresh đều giữ thứ tự này) — map qua row order."""
    cur.execute(
        """SELECT forecast_demand, forecast_version FROM demand_forecast
           WHERE service_run_id=%s AND seat_class=%s
             AND forecast_version=(SELECT COALESCE(MAX(forecast_version),1)
                                   FROM demand_forecast WHERE service_run_id=%s)
           ORDER BY id""",
        (service_run_id, seat_class, service_run_id),
    )
    rows = cur.fetchall()
    by_seg = {i + 1: float(r[0]) for i, r in enumerate(rows)}
    version = rows[0][1] if rows else 1
    return by_seg, version


@router.post("/offers", status_code=201)
def create_offer(req: OfferRequest):
    topology = get_run_topology(req.service_run_id)
    seg_from, seg_to = segment_span(topology, req.origin_station_id, req.dest_station_id)
    ssm = get_state_manager()
    clock = get_clock()

    # 1. Snapshot nhất quán — một lần đọc, dùng cho resolver + LF + remaining
    seatmap = ssm.get_seatmap(req.service_run_id, req.seat_class)
    matrix, seat_ids = _matrix_from_seatmap(seatmap, topology["n_segments"])
    matrix_version = seatmap["matrix_version"]

    # 2-3. Resolver BE3 — same-seat liên tục, reused_gap label thật, rank reused-first
    plan = resolver.best_same_seat(matrix, seat_ids, seg_from, seg_to,
                                    priority_passenger=req.priority_passenger)
    if plan is None:
        # P5 · same-seat rỗng -> thử ghép nhiều ghế (đổi chỗ tại ga dwell >=5').
        # Hành khách ưu tiên KHÔNG BAO GIỜ nhận phương án này (resolver tự lọc rỗng).
        plan = resolver.best_multiseat(
            matrix, seat_ids, [station["id"] for station in topology["stations"]], seg_from, seg_to,
            priority_passenger=req.priority_passenger,
            dwell_minutes={station["id"]: station["dwell_minutes"] for station in topology["stations"]},
            min_dwell_min=MIN_SEAT_CHANGE_DWELL_MIN,
        )
    if plan is None:
        raise NoSameSeatOption(
            "Không tìm được phương án ghế cho hành trình",
            {"origin": req.origin_station_id, "dest": req.dest_station_id},
        )

    # 4. Base fare + policy + forecast từ DB (đã nạp từ seed lúc reset)
    ensure_model_forecast(req.service_run_id)
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT fp.base_fare_vnd, sr.service_date
               FROM fare_product fp
               JOIN service_run sr ON sr.service_run_id = fp.service_run_id
               WHERE fp.service_run_id=%s AND fp.origin_station_id=%s
                 AND fp.dest_station_id=%s AND fp.seat_class=%s
               ORDER BY fp.version DESC LIMIT 1""",
            (req.service_run_id, req.origin_station_id, req.dest_station_id, req.seat_class),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise PolicyUnavailable("Chưa có fare_product cho O-D này", {})
        base_fare = int(row[0])
        service_date = row[1]

        cur.execute(
            """SELECT floor_ratio, ceiling_ratio, max_delta_percent, policy_version FROM pricing_policy
               WHERE is_active=TRUE ORDER BY policy_id DESC LIMIT 1""",
        )
        prow = cur.fetchone()
        if not prow:
            conn.rollback()
            raise PolicyUnavailable("Chưa có pricing policy được approve", {})
        floor_ratio, ceiling_ratio, max_delta_percent, policy_version = prow

        _, forecast_version = _latest_forecast(cur, req.service_run_id, req.seat_class)
    conn.commit()

    # 5. Bid price DLP thật (app.bt3_allocation, cache theo version — xem allocation/cache.py)
    segs = list(range(seg_from, seg_to + 1))
    cached_alloc = allocation_cache.get(req.service_run_id, matrix_version, forecast_version)
    if cached_alloc is None:
        # matrix_version có thể vừa đổi do hold/expire (không tự refresh cache DLP — chỉ
        # reset/forecast-refresh/allocation-refresh mới làm) => cache miss ở đây KHÔNG có
        # nghĩa LP thật sự fail, chỉ là chưa tính cho version mới nhất. Thử tính lại 1 lần
        # trước khi 503 hẳn — refresh() tự đọc seatmap/forecast MỚI NHẤT từ DB nên khớp
        # đúng matrix_version/forecast_version đã snapshot ở bước 1.
        allocation_cache.refresh(req.service_run_id)
        cached_alloc = allocation_cache.get(req.service_run_id, matrix_version, forecast_version)
    if cached_alloc is None:
        raise PolicyUnavailable(
            "Bid price DLP chưa sẵn sàng cho version hiện tại — cần reset/refresh forecast trước", {})
    bp_by_seg = cached_alloc["bid_price_theo_lop"].get(req.seat_class, [0] * topology["n_segments"])
    bid_by_segment = {s: int(bp_by_seg[s - 1]) for s in segs}

    # 6. PricingContext — chỉ tín hiệu hợp pháp; KHÔNG user_id/search-count/device (§2.7)
    now = clock.now()
    lead_time_days = max((service_date - now.date()).days, 0)
    lf = {s: 1.0 - (matrix[:, s - 1] == resolver.FREE).sum() / matrix.shape[0]
          for s in range(1, topology["n_segments"] + 1)}
    journey_lf = [lf[s] for s in segs]
    ctx = PricingContext(
        che_do_gia=_SCENARIO.get("che_do_gia", "AI"),
        lead_time_days=lead_time_days,
        distance_km=distance_km(topology, req.origin_station_id, req.dest_station_id),
        peak_summer=PEAK_SUMMER[0] <= service_date <= PEAK_SUMMER[1],
        tet_window=False,
        load_factor_route=min(journey_lf),
        load_factor_max=max(journey_lf),
    )

    policy = {
        "floor_ratio": float(floor_ratio),
        "ceiling_ratio": float(ceiling_ratio),
        "max_delta_ratio": float(max_delta_percent) / 100.0,
        "csxh": _SEED_POLICY.get("csxh", []),
    }
    versions = {"matrix_version": matrix_version, "forecast_version": forecast_version,
                "policy_version": policy_version}
    service = OfferService(
        engine=PricingEngine(policy, elasticity=get_pricer().elast),
        products=[{"origin_station_id": req.origin_station_id,
                   "dest_station_id": req.dest_station_id,
                   "seat_class": req.seat_class, "gia_goc_vnd": base_fare}],
        versions=versions,
    )
    try:
        offer = service.build_offer(
            service_run_id=req.service_run_id, origin=req.origin_station_id,
            dest=req.dest_station_id, seat_class=req.seat_class,
            seat_plan=plan, pricing_ctx=ctx, bid_by_segment=bid_by_segment,
            safety=None,  # API contract chưa có passenger fields — khách thường
            now=now,
        )
    except PolicyUnavailableError as exc:
        raise PolicyUnavailable(str(exc), {}) from exc

    dr = offer.decision_record
    pb = offer.pricing
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO offer (offer_id, service_run_id, matrix_version, forecast_version, policy_version,
                                   decision, seat_plan, final_price_vnd, expires_at,
                                   origin_station_id, dest_station_id, seat_class)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (offer.offer_id, req.service_run_id, matrix_version, forecast_version, policy_version,
             offer.decision, json.dumps(offer.seat_plan), pb.gia_cuoi_vnd, offer.expires_at,
             req.origin_station_id, req.dest_station_id, req.seat_class),
        )
        cur.execute(
            """INSERT INTO decision_record (decision_id, input_hash, versions, result, base_fare_vnd,
                                             ai_suggested_price_vnd, final_price_vnd, bid_price_total_vnd,
                                             bid_price_breakdown, violations, audit_timeline,
                                             explanation_code, actor, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (dr.decision_id, dr.input_hash, json.dumps(versions), dr.result, dr.base_fare_vnd,
             dr.gia_niem_yet_vnd, dr.gia_cuoi_vnd, dr.bid_total_vnd,
             json.dumps(offer.bid_by_segment), json.dumps(dr.violations),
             json.dumps({"rules_fired": dr.rules_fired, "explanation": dr.explanation}),
             dr.explanation_code, dr.actor, dr.created_at),
        )
    conn.commit()

    if offer.decision == "REJECT":
        raise AllocationRejected(
            "Giá vé không bù đủ chi phí cơ hội các đoạn chiếm dụng",
            {"final_price_vnd": pb.gia_cuoi_vnd, "bid_price_total_vnd": offer.bid_total_vnd,
             "decision_record_id": dr.decision_id},
        )

    return {"data": {
        "offer_id": offer.offer_id,
        "service_run_id": req.service_run_id,
        "matrix_version": matrix_version,
        "forecast_version": forecast_version,
        "policy_version": policy_version,
        "decision": offer.decision,
        "seat_plan": offer.seat_plan,
        "requires_customer_consent": offer.requires_customer_consent,
        "change_station_ids": offer.change_station_ids,
        "so_lan_doi_cho": offer.so_lan_doi_cho,
        "pricing": {
            "gia_goc_vnd": pb.gia_goc_vnd,
            "gia_niem_yet_vnd": pb.gia_niem_yet_vnd,
            "gia_cuoi_vnd": pb.gia_cuoi_vnd,
            "rules_fired": dr.rules_fired,
            "violations": dr.violations,
            "clamped": bool(dr.violations),
            "csxh_doi_tuong": pb.csxh_doi_tuong,
            "che_do_gia": pb.che_do_gia,
        },
        "bid": {"total_vnd": offer.bid_total_vnd, "by_segment": offer.bid_by_segment},
        "decision_record_id": dr.decision_id,
        "explanation": dr.explanation,
        "expires_at": offer.expires_at,
    }}


@router.post("/offers/{offer_id}/override")
def override_offer_price(offer_id: str, body: OverrideRequest,
                         x_actor_role: str = Header(..., alias="X-Actor-Role")):
    """P7.6 — điều độ viên ghi đè giá TRONG sàn-trần đã duyệt, chỉ khi offer chưa có
    hold (giá đã khoá thì bất khả xâm phạm)."""
    require_approver_role(x_actor_role)
    conn = get_connection()
    return {"data": override_service.override_price(conn, offer_id, body.new_price_vnd,
                                                     body.reason, body.decided_by)}

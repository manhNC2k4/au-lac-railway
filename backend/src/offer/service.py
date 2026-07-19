# -*- coding: utf-8 -*-
"""BE3 · OfferService — pipeline bất di bất dịch (Master §8, DEV3 §H6-H10):

    seat plan → base fare (O-D) → price proposal → guardrail → so bid → offer

Offer IMMUTABLE, có expiry, đủ 4 version. TẠO OFFER KHÔNG GIỮ GHẾ (bước 8, không phải 9 —
giữ ghế là việc BE1 ở /holds). DecisionRecord append-only: input_hash, versions, result,
rules đã bắn, violations, explanation — đây chính là nhật ký quyết định/phê duyệt + XAI.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from ..merging.resolver import MergedSeatPlan, SeatPlan
from ..pricing.context import PricingContext, SafetyContext
from ..pricing.engine import PricingBreakdown, PricingEngine, fare_product_od

OFFER_TTL_SECONDS = 900  # Giá đã đề xuất có hiệu lực 15 phút trước khi khách giữ chỗ.


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    input_hash: str
    service_run_id: str
    matrix_version: int
    forecast_version: int
    policy_version: int
    result: str                       # ACCEPT | REJECT
    base_fare_vnd: int
    gia_niem_yet_vnd: int
    gia_cuoi_vnd: int
    bid_total_vnd: int
    rules_fired: list[dict]
    violations: list[str]             # rang_buoc_cham chạm (SAN/TRAN/MAX_DELTA/FREEZE)
    explanation_code: str
    explanation: str
    actor: str
    created_at: str


@dataclass(frozen=True)
class Offer:
    offer_id: str
    service_run_id: str
    matrix_version: int
    forecast_version: int
    policy_version: int
    decision: str
    seat_plan: list[dict]             # >=2 leg ⇒ ghép nhiều ghế (P5)
    requires_customer_consent: bool
    change_station_ids: list[str]
    so_lan_doi_cho: int
    pricing: PricingBreakdown
    bid_total_vnd: int
    bid_by_segment: dict
    decision_record: DecisionRecord
    expires_at: str


def _seat_plan_legs(plan: SeatPlan | MergedSeatPlan) -> list[dict]:
    if isinstance(plan, MergedSeatPlan):
        return [{"seat_id": leg.seat_id, "segment_from": leg.segment_from,
                  "segment_to": leg.segment_to, "reused_gap": False,
                  "requires_seat_change": True} for leg in plan.legs]
    return [{"seat_id": plan.seat_id, "segment_from": plan.segment_from,
              "segment_to": plan.segment_to, "reused_gap": plan.reused_gap,
              "requires_seat_change": plan.requires_seat_change}]


def _input_hash(*parts) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _explain(pb: PricingBreakdown, decision: str, bid_total: int) -> tuple[str, str]:
    fired = ", ".join(f"{r.rule_id}(×{r.he_so})" for r in pb.rules_fired) or "không luật động"
    csxh = "" if pb.csxh_muc_giam == 0 else f"; CSXH {pb.csxh_doi_tuong} -{pb.csxh_muc_giam:.0%} (áp sau cùng)"
    clamp = f"; chạm {'/'.join(pb.rang_buoc_cham)}" if pb.rang_buoc_cham else ""
    code = "ACCEPT_BID_COVERED" if decision == "ACCEPT" else "REJECT_BID_UNCOVERED"
    text = (f"F0={pb.gia_goc_vnd}đ → {fired} → niêm yết {pb.gia_niem_yet_vnd}đ{clamp}{csxh} "
            f"→ cuối {pb.gia_cuoi_vnd}đ vs Σbid {bid_total}đ ⇒ {decision}")
    return code, text


@dataclass
class OfferService:
    engine: PricingEngine
    products: list[dict]
    versions: dict                   # {matrix_version, forecast_version, policy_version}
    actor: str = "system"

    def build_offer(
        self, *, service_run_id: str, origin: str, dest: str, seat_class: str,
        seat_plan: SeatPlan | MergedSeatPlan, pricing_ctx: PricingContext,
        bid_by_segment: dict[int, int],
        safety: SafetyContext | None = None, now: datetime | None = None,
    ) -> Offer:
        now = now or datetime.now(timezone.utc)
        f0 = fare_product_od(self.products, origin, dest, seat_class)   # giá O-D, KHÔNG cộng leg
        bid_total = sum(bid_by_segment.values())
        pb: PricingBreakdown = self.engine.price(f0, pricing_ctx, safety, bid_total_vnd=bid_total)

        decision = "ACCEPT" if pb.gia_cuoi_vnd >= bid_total else "REJECT"
        code, text = _explain(pb, decision, bid_total)

        legs = _seat_plan_legs(seat_plan)
        is_merged = isinstance(seat_plan, MergedSeatPlan)
        ih = _input_hash(service_run_id, origin, dest, seat_class, legs,
                         asdict(pricing_ctx), sorted(bid_by_segment.items()), self.versions)
        dr = DecisionRecord(
            decision_id=f"dr_{uuid.uuid4().hex[:12]}", input_hash=ih,
            service_run_id=service_run_id, **self.versions, result=decision,
            base_fare_vnd=f0, gia_niem_yet_vnd=pb.gia_niem_yet_vnd, gia_cuoi_vnd=pb.gia_cuoi_vnd,
            bid_total_vnd=bid_total, rules_fired=[asdict(r) for r in pb.rules_fired],
            violations=list(pb.rang_buoc_cham), explanation_code=code, explanation=text,
            actor=self.actor, created_at=now.isoformat(),
        )
        return Offer(
            offer_id=f"offer_{uuid.uuid4().hex[:12]}", service_run_id=service_run_id,
            **self.versions, decision=decision, seat_plan=legs,
            requires_customer_consent=is_merged and seat_plan.requires_customer_consent,
            change_station_ids=list(seat_plan.change_station_ids) if is_merged else [],
            so_lan_doi_cho=seat_plan.so_lan_doi_cho if is_merged else 0,
            pricing=pb, bid_total_vnd=bid_total,
            bid_by_segment={str(k): v for k, v in bid_by_segment.items()},
            decision_record=dr, expires_at=(now + timedelta(seconds=OFFER_TTL_SECONDS)).isoformat(),
        )

# -*- coding: utf-8 -*-
"""BE3 · PricingEngine — F0 (giá gốc O-D) → đề xuất giá động → guardrail → CSXH (max, sau cùng).

P3 (MODEL_BASE_INTEGRATION_PLAN §P3): đề xuất giá động dùng optimizer elasticity thật
(`app.elasticity.Elasticity`, ước lượng từ search_log) — max E[đóng góp]=P(mua|r)·(p−c),
c=Σ bid DLP hành trình (P2). Trần động r≤1+0.15·LF_max, sàn r≥1−0.05·(1−LF_max) (dải hẹp
quanh F0, tránh ngoại suy vùng thiên lệch — xem app/bt5_pricing.py). Mùa vụ (hè/Tết) đọc từ
`models/artifacts/bt5_pricing_params.json` (hệ số DGP thật, không gõ tay). Không nạp được
elasticity (artifact thiếu / chưa boot Pricer) ⇒ fallback mùa-vụ-only, KHÔNG bịa hệ số động.

Guardrail đúng thứ tự (DEV3 §Guardrail), KHÔNG đảo — giữ nguyên tuyệt đối qua P3:
  1. Policy TỒN TẠI & approved  → thiếu ⇒ PolicyUnavailable (503, KHÔNG default giá)
  2. clip sàn / trần
  3. max delta (chỉ khi có giá công bố trước)
  4. round_to_1k
  5. freeze
CSXH áp SAU guardrail: MAX một mức, nhân (1 - muc_giam), round — Điều 40 NĐ 16/2026.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:          # `app/` package sống ở repo root, ngoài backend/
    sys.path.insert(0, str(REPO_ROOT))

from app.config import DEFAULT_POLICY        # noqa: E402 — sau khi chỉnh sys.path

from ..forecast.bid_price import round_to_1k
from .context import PricingContext, SafetyContext

PRICING_PARAMS_PATH = REPO_ROOT / "models" / "artifacts" / "bt5_pricing_params.json"


def _load_delta_mua(path: Path = PRICING_PARAMS_PATH) -> dict:
    """Hệ số mùa vụ DGP thật (models/export_bt5_params.py) — nguồn duy nhất, không gõ tay."""
    return json.loads(path.read_text(encoding="utf-8"))["delta_mua"]


DELTA_MUA = _load_delta_mua()


class PolicyUnavailableError(Exception):
    """Không có policy approved ⇒ fail closed (503), tuyệt đối không bán giá mặc định."""


@dataclass(frozen=True)
class RuleFired:
    rule_id: str
    he_so: float
    thu_tu: int


@dataclass(frozen=True)
class PricingBreakdown:
    gia_goc_vnd: int                      # F0 (giá gốc O-D)
    gia_niem_yet_vnd: int                 # sau luật động + guardrail
    gia_cuoi_vnd: int                     # sau CSXH
    rules_fired: list[RuleFired]
    rang_buoc_cham: list[str]             # "SAN" | "TRAN" | "MAX_DELTA" | "FREEZE"
    csxh_doi_tuong: str
    csxh_muc_giam: float
    che_do_gia: str


def _delta_mua(ctx: PricingContext) -> tuple[float, str]:
    """Mùa vụ thật (bt5_pricing_params.json) — Tết ưu tiên hơn hè khi cả hai đúng (hiếm)."""
    if ctx.tet_window:
        return DELTA_MUA["tet"], "MUA_VU:TET"
    if ctx.peak_summer:
        return DELTA_MUA["he"], "MUA_VU:HE"
    return 0.0, ""


def apply_dynamic(f0: int, ctx: PricingContext, bid_total_vnd: int,
                  elasticity) -> tuple[float, list[RuleFired]]:
    """Đề xuất giá động = mùa vụ (real DGP) [+ elasticity optimizer nếu artifact có nạp].

    elasticity=None (Pricer/artifact chưa boot) ⇒ fallback mùa-vụ-only, KHÔNG suy đoán hệ số
    khan hiếm — guardrail/CSXH phía sau vẫn chạy nguyên vẹn nên vẫn tất định & trong biên."""
    dmua, dmua_id = _delta_mua(ctx)
    fired: list[RuleFired] = []
    if dmua_id:
        fired.append(RuleFired(dmua_id, round(1 + dmua, 4), 1))

    if elasticity is None:
        return f0 * (1 + dmua), fired

    lf_max = min(max(ctx.load_factor_max, 0.0), 1.0)
    is_tet = ctx.tet_window
    ceil_r = 1.0 + DEFAULT_POLICY["elastic_markup_max"] * lf_max
    floor_r = 1.0 - DEFAULT_POLICY["elastic_markdown_max"] * (1.0 - lf_max)
    if is_tet:
        ceil_r = max(ceil_r, 1.0 + dmua + DEFAULT_POLICY["elastic_markup_max"] * lf_max)
        floor_r = max(floor_r, 1.0 + dmua)
    floor_r = min(floor_r, ceil_r)

    opt = elasticity.optimal_price(f0, bid_total_vnd, ctx.distance_km, is_tet,
                                   ctx.lead_time_days, floor_r, ceil_r)
    fired.append(RuleFired(f"ELASTIC:r={opt['r']:.2f}", round(opt["r"], 4), 2))
    return float(opt["p"]), fired


def apply_guardrail(f0: int, price: float, policy: dict | None,
                    previous_price: int | None = None) -> tuple[int, list[str]]:
    if policy is None:
        raise PolicyUnavailableError("Không có pricing policy approved (fail closed 503)")
    if policy.get("frozen"):
        return round_to_1k(f0), ["FREEZE"]

    touched: list[str] = []
    lo = f0 * policy["floor_ratio"]
    hi = f0 * policy["ceiling_ratio"]
    if price < lo:
        price, _ = lo, touched.append("SAN")
    elif price > hi:
        price, _ = hi, touched.append("TRAN")

    if previous_price is not None:
        md = policy.get("max_delta_ratio", 1.0)
        d_lo, d_hi = previous_price * (1 - md), previous_price * (1 + md)
        if price < d_lo or price > d_hi:
            price = min(max(price, d_lo), d_hi)
            touched.append("MAX_DELTA")

    return round_to_1k(price), touched


def csxh_apply(gia_niem_yet: int, entitlements, csxh_table: list[dict]) -> tuple[str, float, int]:
    """MAX một mức giảm đủ điều kiện, áp SAU cùng (Điều 40). KHÔNG cộng dồn."""
    eligible = [(c["doi_tuong"], c["muc_giam_ty_le"]) for c in csxh_table
                if c["doi_tuong"] in set(entitlements)]
    if not eligible:
        return "KHONG", 0.0, gia_niem_yet
    ten, muc = max(eligible, key=lambda t: t[1])
    return ten, muc, round_to_1k(gia_niem_yet * (1 - muc))


@dataclass
class PricingEngine:
    policy: dict                          # từ seed/pricing_policy.json (có floor/ceiling/csxh)
    elasticity: object | None = None      # app.elasticity.Elasticity, nạp lúc boot (deps.get_pricer().elast)

    def price(self, f0: int, ctx: PricingContext, safety: SafetyContext | None = None,
              previous_price: int | None = None, bid_total_vnd: int = 0) -> PricingBreakdown:
        raw, fired = apply_dynamic(f0, ctx, bid_total_vnd, self.elasticity)
        gia_niem_yet, touched = apply_guardrail(f0, raw, self.policy, previous_price)
        entitlements = safety.entitlements if safety else ()
        ten, muc, gia_cuoi = csxh_apply(gia_niem_yet, entitlements, self.policy.get("csxh", []))
        return PricingBreakdown(
            gia_goc_vnd=f0, gia_niem_yet_vnd=gia_niem_yet, gia_cuoi_vnd=gia_cuoi,
            rules_fired=fired, rang_buoc_cham=touched,
            csxh_doi_tuong=ten, csxh_muc_giam=muc, che_do_gia=ctx.che_do_gia,
        )


def fare_product_od(products: list[dict], origin: str, dest: str, seat_class: str) -> int:
    """Giá GỐC O-D — tra trực tiếp, KHÔNG cộng giá từng leg (G06). Thiếu O-D ⇒ ValueError."""
    for p in products:
        if (p["origin_station_id"] == origin and p["dest_station_id"] == dest
                and p["seat_class"] == seat_class):
            return int(p["gia_goc_vnd"])
    raise ValueError(f"Không có FareProduct O-D {origin}->{dest} ({seat_class})")

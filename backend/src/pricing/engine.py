# -*- coding: utf-8 -*-
"""BE3 · PricingEngine — F0 (giá gốc O-D) → luật động (YAML) → guardrail → CSXH (max, sau cùng).

Thứ tự phép toán & tham số bám class Pricer (generate_data.py:404) — đã kiểm chứng 7,6tr vé,
0 vi phạm. Chép LOGIC không chép cấu trúc (Pricer là batch; đây là per-request + audit trail).

Guardrail đúng thứ tự (DEV3 §Guardrail), KHÔNG đảo:
  1. Policy TỒN TẠI & approved  → thiếu ⇒ PolicyUnavailable (503, KHÔNG default giá)
  2. clip sàn / trần
  3. max delta (chỉ khi có giá công bố trước)
  4. round_to_1k
  5. freeze
CSXH áp SAU guardrail: MAX một mức, nhân (1 - muc_giam), round — Điều 40 NĐ 16/2026.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..forecast.bid_price import round_to_1k
from .context import PricingContext, SafetyContext

RULES_PATH = Path(__file__).resolve().parents[2] / "rules" / "pricing_rules.yaml"


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


def _match(cond_key: str, cond_val, ctx: dict) -> bool:
    for suf, op in (("_gte", ">="), ("_lte", "<="), ("_gt", ">"), ("_lt", "<")):
        if cond_key.endswith(suf):
            attr = cond_key[: -len(suf)]
            if attr not in ctx:
                return False
            x, y = ctx[attr], cond_val
            return {">=": x >= y, "<=": x <= y, ">": x > y, "<": x < y}[op]
    return ctx.get(cond_key) == cond_val


def load_rules(path: Path = RULES_PATH) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return sorted(doc["rules"], key=lambda r: r["thu_tu"])


def apply_rules(f0: int, ctx: PricingContext, rules: list[dict]) -> tuple[float, list[RuleFired]]:
    cvals = {
        "che_do_gia": ctx.che_do_gia, "lead_time_days": ctx.lead_time_days,
        "distance_km": ctx.distance_km, "peak_summer": ctx.peak_summer,
        "tet_window": ctx.tet_window, "load_factor_route": ctx.load_factor_route,
        "load_factor_max": ctx.load_factor_max,
    }
    price = float(f0)
    fired: list[RuleFired] = []
    for r in rules:
        if all(_match(k, v, cvals) for k, v in r.get("when", {}).items()):
            price *= r["he_so"]
            fired.append(RuleFired(r["rule_id"], r["he_so"], r["thu_tu"]))
    return price, fired


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
    rules: list[dict] = field(default_factory=load_rules)

    def price(self, f0: int, ctx: PricingContext, safety: SafetyContext | None = None,
              previous_price: int | None = None) -> PricingBreakdown:
        raw, fired = apply_rules(f0, ctx, self.rules)
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

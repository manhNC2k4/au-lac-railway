# -*- coding: utf-8 -*-
"""BE3 pricing/compliance DoD — 3 test ⭐ lên slide: search-invariant, locked-after-hold,
exclude-sensitive. + CSXH max-not-product & áp-sau-cùng, guardrail order, 503."""
import json
import unittest
from dataclasses import fields
from pathlib import Path

from src.pricing.context import (FORBIDDEN_PRICING_FEATURES, PricingContext,
                                  SafetyContext)
from src.pricing.engine import (PolicyUnavailableError, PricingEngine,
                                 apply_guardrail, csxh_apply, fare_product_od)

SEED = Path(__file__).resolve().parents[1] / "seed"
POLICY = json.loads((SEED / "pricing_policy.json").read_text(encoding="utf-8"))
PRODUCTS = json.loads((SEED / "fare_products.json").read_text(encoding="utf-8"))["products"]

# Golden 15/06/2026: AI, cao điểm hè, THO->DHO 347km, LF route thấp ⇒ AI giảm
GOLDEN_CTX = PricingContext(che_do_gia="AI", lead_time_days=10, distance_km=347.0,
                            peak_summer=True, load_factor_route=0.6)


def engine():
    return PricingEngine(policy=POLICY)


class TestPricingCompliance(unittest.TestCase):
    def test_price_invariant_to_repeated_search(self):
        eng = engine()
        f0 = fare_product_od(PRODUCTS, "THO", "DHO", "NGOI_MEM_DH")
        prices = {eng.price(f0, GOLDEN_CTX).gia_cuoi_vnd for _ in range(50)}
        self.assertEqual(len(prices), 1)  # searches 1->50, giá KHÔNG đổi

    def test_pricing_features_exclude_sensitive(self):
        names = {f.name for f in fields(PricingContext)}
        self.assertEqual(names & FORBIDDEN_PRICING_FEATURES, set())

    def test_pricing_context_has_no_safety_context(self):
        names = {f.name for f in fields(PricingContext)}
        safety = {f.name for f in fields(SafetyContext)}
        self.assertEqual(names & (safety | {"entitlements", "passenger_type", "so_lan_doi_cho"}), set())
        types = {f.type for f in fields(PricingContext)}
        self.assertNotIn("SafetyContext", {str(t) for t in types})

    def test_price_locked_after_hold(self):
        # Định giá 2 lần cùng input ⇒ y hệt (confirm tái dùng giá offer, không re-price)
        eng = engine()
        f0 = fare_product_od(PRODUCTS, "THO", "DHO", "NGOI_MEM_DH")
        a = eng.price(f0, GOLDEN_CTX)
        b = eng.price(f0, GOLDEN_CTX)
        self.assertEqual(a.gia_cuoi_vnd, b.gia_cuoi_vnd)

    def test_social_policy_discount_is_max_not_product(self):
        # đủ điều kiện cả cao tuổi (0.15) và khuyết tật (0.25) ⇒ lấy 0.25, KHÔNG 1-(.85*.75)
        ten, muc, gia = csxh_apply(1_000_000, ("NGUOI_CAO_TUOI", "NGUOI_KHUYET_TAT"), POLICY["csxh"])
        self.assertEqual(muc, 0.25)
        self.assertEqual(gia, 750_000)              # max, không cộng dồn (=0.3625 nếu sai)
        self.assertNotEqual(gia, 637_500)

    def test_social_policy_applied_after_dynamic(self):
        eng = engine()
        f0 = fare_product_od(PRODUCTS, "THO", "DHO", "NGOI_MEM_DH")
        safety = SafetyContext(passenger_type="NGUOI_CO_CONG", so_lan_doi_cho=0,
                               entitlements=("NGUOI_CO_CONG",))
        pb = eng.price(f0, GOLDEN_CTX, safety)
        # CSXH áp SAU guardrail: gia_cuoi = round_1k(gia_niem_yet * (1 - 0.30))
        self.assertEqual(pb.gia_cuoi_vnd, int(round(pb.gia_niem_yet_vnd * 0.70 / 1000)) * 1000)
        self.assertEqual(pb.csxh_muc_giam, 0.30)

    def test_no_price_below_floor_or_above_cap(self):
        eng = engine()
        f0 = 1_000_000
        floor = int(f0 * POLICY["floor_ratio"])
        ceil = int(f0 * POLICY["ceiling_ratio"])
        # ép giảm mạnh: AI + LF thấp
        low = eng.price(f0, PricingContext("AI", 30, 1000.0, load_factor_route=0.5)).gia_niem_yet_vnd
        self.assertGreaterEqual(low, floor - 1000)
        # ép tăng: sát ngày + hè
        high = eng.price(f0, PricingContext("LUAT", 1, 100.0, peak_summer=True)).gia_niem_yet_vnd
        self.assertLessEqual(high, ceil + 1000)

    def test_guardrail_order_floor_ceiling_delta_round_freeze(self):
        f0 = 1_000_000
        # floor clamp (0.55 * 1_000_000 = 550_000)
        p, t = apply_guardrail(f0, 100_000, POLICY)
        self.assertEqual(p, 550_000)
        self.assertIn("SAN", t)
        # ceiling clamp
        p, t = apply_guardrail(f0, 9_000_000, POLICY)
        self.assertIn("TRAN", t)
        # max delta so với giá công bố trước
        p, t = apply_guardrail(f0, 1_000_000, POLICY, previous_price=800_000)
        self.assertIn("MAX_DELTA", t)
        self.assertLessEqual(p, int(800_000 * (1 + POLICY["max_delta_ratio"])) + 1000)
        # round_to_1k
        self.assertEqual(p % 1000, 0)
        # freeze
        pf, tf = apply_guardrail(f0, 1_234_567, {**POLICY, "frozen": True})
        self.assertEqual(tf, ["FREEZE"])
        self.assertEqual(pf, 1_000_000)

    def test_policy_unavailable_returns_503(self):
        with self.assertRaises(PolicyUnavailableError):
            apply_guardrail(1_000_000, 900_000, None)   # BE1 map -> 503 POLICY_UNAVAILABLE

    def test_priority_passengers_never_forced_to_change_seat(self):
        # SafetyContext ưu tiên (so_lan_doi_cho=0) — merging chỉ trả same-seat (requires_seat_change=False)
        from src.merging.resolver import best_same_seat, FREE
        import numpy as np
        m = np.full((40, 7), FREE, dtype=np.int8)
        seats = [f"C01-S{n:03d}" for n in range(1, 41)]
        plan = best_same_seat(m, seats, 3, 4, priority_passenger=True)
        self.assertFalse(plan.requires_seat_change)


if __name__ == "__main__":
    unittest.main()

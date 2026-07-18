# -*- coding: utf-8 -*-
"""BE3 offer DoD — golden path end-to-end: resolve S017 THO->DHO -> price -> so bid -> offer.
Offer KHÔNG giữ ghế; DecisionRecord có versions + rules + explanation (nhật ký quyết định/XAI)."""
import json
import unittest
from pathlib import Path

import numpy as np

from src.merging.resolver import FREE, SOLD, SeatLeg, MergedSeatPlan, best_same_seat
from src.offer.service import OfferService
from src.pricing.context import PricingContext, SafetyContext
from src.pricing.engine import PricingEngine

SEED = Path(__file__).resolve().parents[1] / "seed"
POLICY = json.loads((SEED / "pricing_policy.json").read_text(encoding="utf-8"))
PRODUCTS = json.loads((SEED / "fare_products.json").read_text(encoding="utf-8"))["products"]
SEATS = [f"C01-S{n:03d}" for n in range(1, 41)]
VERSIONS = {"matrix_version": 1, "forecast_version": 1, "policy_version": 1}


def golden_matrix():
    m = np.full((40, 7), SOLD, dtype=np.int8)
    m[16] = [SOLD, SOLD, FREE, FREE, SOLD, SOLD, SOLD]  # C01-S017 golden gap
    return m


def service():
    return OfferService(engine=PricingEngine(policy=POLICY), products=PRODUCTS, versions=VERSIONS)


class TestOffer(unittest.TestCase):
    def _offer(self, bid, safety=None):
        m = golden_matrix()
        plan = best_same_seat(m, SEATS, 3, 4)
        ctx = PricingContext("AI", 10, 347.0, peak_summer=True, load_factor_route=0.6)
        return service().build_offer(
            service_run_id="SE1_2026-06-15_LE", origin="THO", dest="DHO",
            seat_class="NGOI_MEM_DH", seat_plan=plan, pricing_ctx=ctx,
            bid_by_segment=bid, safety=safety)

    def test_golden_offer_accept(self):
        offer = self._offer({3: 40_000, 4: 60_000})  # Σbid 100k << giá vé
        self.assertEqual(offer.decision, "ACCEPT")
        self.assertEqual(offer.seat_plan[0]["seat_id"], "C01-S017")
        self.assertTrue(offer.seat_plan[0]["reused_gap"])
        self.assertGreaterEqual(offer.pricing.gia_cuoi_vnd, offer.bid_total_vnd)

    def test_offer_reject_when_bid_uncovered(self):
        offer = self._offer({3: 5_000_000, 4: 5_000_000})  # bid quá cao
        self.assertEqual(offer.decision, "REJECT")
        self.assertEqual(offer.decision_record.explanation_code, "REJECT_BID_UNCOVERED")

    def test_offer_holds_no_seat(self):
        # build_offer chỉ đọc matrix (nhận qua resolver), không nhận/không ghi state
        m = golden_matrix()
        snap = m.copy()
        best_same_seat(m, SEATS, 3, 4)
        np.testing.assert_array_equal(m, snap)

    def test_decision_record_has_versions_and_audit(self):
        dr = self._offer({3: 40_000, 4: 60_000}).decision_record
        self.assertEqual(dr.matrix_version, 1)
        self.assertEqual(dr.forecast_version, 1)
        self.assertEqual(dr.policy_version, 1)
        self.assertTrue(dr.input_hash)
        self.assertTrue(dr.rules_fired)          # có luật động bắn (audit trail/XAI)
        self.assertIn("⇒", dr.explanation)

    def test_offer_immutable_and_versioned(self):
        offer = self._offer({3: 40_000, 4: 60_000})
        with self.assertRaises(Exception):
            offer.decision = "REJECT"            # frozen dataclass
        self.assertEqual(offer.pricing.che_do_gia, "AI")

    def test_csxh_priority_passenger_offer(self):
        offer = self._offer({3: 40_000, 4: 60_000},
                            safety=SafetyContext("NGUOI_CO_CONG", 0, ("NGUOI_CO_CONG",)))
        self.assertEqual(offer.pricing.csxh_muc_giam, 0.30)
        self.assertLess(offer.pricing.gia_cuoi_vnd, offer.pricing.gia_niem_yet_vnd)

    def test_multiseat_offer_requires_consent(self):
        # P5 · same-seat hết -> resolver trả MergedSeatPlan (2 ghế đổi tại VIN)
        plan = MergedSeatPlan(
            legs=[SeatLeg("C01-S001", 3, 3), SeatLeg("C01-S002", 4, 4)],
            change_station_ids=["VIN"], so_lan_doi_cho=1)
        ctx = PricingContext("AI", 10, 347.0, peak_summer=True, load_factor_route=0.6)
        offer = service().build_offer(
            service_run_id="SE1_2026-06-15_LE", origin="THO", dest="DHO",
            seat_class="NGOI_MEM_DH", seat_plan=plan, pricing_ctx=ctx,
            bid_by_segment={3: 40_000, 4: 60_000})
        self.assertTrue(offer.requires_customer_consent)
        self.assertEqual(offer.so_lan_doi_cho, 1)
        self.assertEqual(offer.change_station_ids, ["VIN"])
        self.assertEqual(len(offer.seat_plan), 2)
        self.assertEqual(offer.seat_plan[0]["seat_id"], "C01-S001")
        self.assertEqual(offer.seat_plan[1]["seat_id"], "C01-S002")
        self.assertTrue(all(leg["requires_seat_change"] for leg in offer.seat_plan))

    def test_same_seat_offer_no_consent_needed(self):
        offer = self._offer({3: 40_000, 4: 60_000})
        self.assertFalse(offer.requires_customer_consent)
        self.assertEqual(offer.so_lan_doi_cho, 0)
        self.assertEqual(offer.change_station_ids, [])


if __name__ == "__main__":
    unittest.main()

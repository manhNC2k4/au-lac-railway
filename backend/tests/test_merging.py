# -*- coding: utf-8 -*-
"""BE3 merging DoD — golden gap, không trả leg HELD/SOLD, label reused_gap, không dời SOLD, <200ms."""
import time
import unittest

import numpy as np

from src.merging.resolver import (FREE, HELD, SOLD, best_multiseat,
                                   best_same_seat, continuous_same_seat,
                                   resolve_multiseat_options, resolve_same_seat_options)

STATION_IDS = ["HNO", "NBI", "THO", "VIN", "DHO", "HUE", "DNA", "SGO"]  # 8 ga golden

SEATS = [f"C01-S{n:03d}" for n in range(1, 41)]
S017 = 16  # index của C01-S017
# THO(idx2)->DHO(idx4): seg_from=3, seg_to=4
SEG_FROM, SEG_TO = 3, 4


def golden_matrix() -> np.ndarray:
    """Chỉ C01-S017 có golden gap: SOLD L1-2, FREE L3-4, SOLD L5-7. Còn lại SOLD toàn bộ."""
    m = np.full((40, 7), SOLD, dtype=np.int8)
    m[S017] = [SOLD, SOLD, FREE, FREE, SOLD, SOLD, SOLD]
    return m


class TestMerging(unittest.TestCase):
    def test_golden_gap_found(self):
        m = golden_matrix()
        idxs = continuous_same_seat(m, SEG_FROM, SEG_TO)
        self.assertEqual(list(idxs), [S017])
        plan = best_same_seat(m, SEATS, SEG_FROM, SEG_TO)
        self.assertEqual(plan.seat_id, "C01-S017")
        self.assertEqual((plan.segment_from, plan.segment_to), (3, 4))

    def test_no_held_or_sold_leg_returned(self):
        m = np.full((40, 7), FREE, dtype=np.int8)
        m[5, 2] = SOLD   # ghế 5 SOLD ở seg3 (trong span)
        m[6, 3] = HELD   # ghế 6 HELD ở seg4 (trong span)
        idxs = set(continuous_same_seat(m, SEG_FROM, SEG_TO).tolist())
        self.assertNotIn(5, idxs)
        self.assertNotIn(6, idxs)

    def test_reused_gap_label_correct(self):
        m = golden_matrix()
        plan = best_same_seat(m, SEATS, SEG_FROM, SEG_TO)
        self.assertTrue(plan.reused_gap)  # có SOLD trước seg3 và sau seg4
        # ghế FREE hoàn toàn ⇒ reused_gap False
        m2 = np.full((40, 7), FREE, dtype=np.int8)
        self.assertFalse(best_same_seat(m2, SEATS, SEG_FROM, SEG_TO).reused_gap)

    def test_reused_gap_ranked_first(self):
        # 1 ghề reused-gap + 1 ghế trống hoàn toàn ⇒ reused xếp trước (mục tiêu ghép chặng)
        m = np.full((40, 7), FREE, dtype=np.int8)
        m[3] = [SOLD, SOLD, FREE, FREE, SOLD, SOLD, SOLD]  # reused gap
        opts = resolve_same_seat_options(m, SEATS, SEG_FROM, SEG_TO)
        self.assertTrue(opts[0].reused_gap)

    def test_sold_bookings_never_moved(self):
        m = golden_matrix()
        snapshot = m.copy()
        _ = resolve_same_seat_options(m, SEATS, SEG_FROM, SEG_TO)
        np.testing.assert_array_equal(m, snapshot)  # resolver read-only, 0 mutation

    def test_resolver_under_200ms(self):
        m = golden_matrix()
        t0 = time.perf_counter()
        for _ in range(1000):
            continuous_same_seat(m, SEG_FROM, SEG_TO)
        self.assertLess((time.perf_counter() - t0) / 1000, 0.2)


class TestMultiseat(unittest.TestCase):
    """P5 · ghép nhiều ghế (đổi chỗ) — gọi khi same-seat rỗng."""

    def _split_matrix(self) -> np.ndarray:
        """Không ghế nào FREE cả L3 lẫn L4; ghế0 FREE mỗi L3, ghế1 FREE mỗi L4."""
        m = np.full((40, 7), SOLD, dtype=np.int8)
        m[0, 2] = FREE   # C01-S001 free L3
        m[1, 3] = FREE   # C01-S002 free L4
        return m

    def test_same_seat_empty_but_multiseat_covers(self):
        m = self._split_matrix()
        self.assertEqual(list(continuous_same_seat(m, SEG_FROM, SEG_TO)), [])  # same-seat hết
        plans = resolve_multiseat_options(m, SEATS, STATION_IDS, SEG_FROM, SEG_TO)
        self.assertEqual(len(plans), 1)
        p = plans[0]
        self.assertEqual(p.so_lan_doi_cho, 1)
        self.assertEqual([(l.seat_id, l.segment_from, l.segment_to) for l in p.legs],
                         [("C01-S001", 3, 3), ("C01-S002", 4, 4)])
        self.assertEqual(p.change_station_ids, ["VIN"])  # biên seg3/seg4
        self.assertTrue(p.requires_seat_change and p.requires_customer_consent)

    def test_priority_passenger_never_gets_multiseat(self):
        m = self._split_matrix()
        self.assertEqual(
            resolve_multiseat_options(m, SEATS, STATION_IDS, SEG_FROM, SEG_TO,
                                      priority_passenger=True), [])

    def test_dwell_too_short_blocks_change_point(self):
        m = self._split_matrix()
        # VIN dwell 2' < 5' -> không được đổi chỗ tại VIN -> không có phương án
        plans = resolve_multiseat_options(m, SEATS, STATION_IDS, SEG_FROM, SEG_TO,
                                          dwell_minutes={"VIN": 2.0})
        self.assertEqual(plans, [])

    def test_configured_three_minute_dwell_allows_demo_change(self):
        m = self._split_matrix()
        plans = resolve_multiseat_options(
            m, SEATS, STATION_IDS, SEG_FROM, SEG_TO,
            dwell_minutes={"VIN": 3.0}, min_dwell_min=3.0,
        )
        self.assertEqual(len(plans), 1)

    def test_deterministic(self):
        m = self._split_matrix()
        a = best_multiseat(m, SEATS, STATION_IDS, SEG_FROM, SEG_TO)
        b = best_multiseat(m, SEATS, STATION_IDS, SEG_FROM, SEG_TO)
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_golden_single_seat_still_wins_no_multiseat(self):
        # golden gap có ghế same-seat -> KHÔNG động tới nhánh multiseat (luồng chính không đổi)
        m = golden_matrix()
        self.assertEqual(list(continuous_same_seat(m, SEG_FROM, SEG_TO)), [S017])


if __name__ == "__main__":
    unittest.main()

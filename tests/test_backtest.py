# -*- coding: utf-8 -*-
"""DoD tests — DEV2_BE_DATA_FORECAST_BACKTEST.md §Test bắt buộc (backtest phần).
Run: python -m unittest tests.test_backtest -v   (từ repo root)
"""
import unittest
from pathlib import Path

from src.backtest import engine, events
from src.forecast import network

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestGoldenRequest(unittest.TestCase):
    def test_baseline_rejects_golden_request(self):
        """⭐ demo vô nghĩa nếu test này fail (DEV2 §Test bắt buộc)."""
        baseline, aulac = engine.build_golden_state()
        seg_from, seg_to = network.seg_range(*network.GOLDEN_OD)
        self.assertFalse(baseline.request(seg_from, seg_to, 1))

    def test_aulac_serves_golden_gap_on_golden_seat(self):
        baseline, aulac = engine.build_golden_state()
        seg_from, seg_to = network.seg_range(*network.GOLDEN_OD)
        seat_idx = aulac.first_fit(seg_from, seg_to)
        self.assertEqual(seat_idx, engine.GOLDEN_SEAT_IDX)


class TestBacktestEngine(unittest.TestCase):
    def setUp(self):
        self.events_a = events.generate_events(20260717)
        self.events_by_seed = {s: events.generate_events(s) for s in events.SEEDS}

    def test_same_event_checksum_both_strategies(self):
        """Common random numbers: baseline và Âu Lạc phải dùng ĐÚNG cùng event stream."""
        before = events.checksum(self.events_a)
        baseline_state = engine.BaselineQuota()
        aulac_state = engine.SegmentSeatMatrix(network.N_SEATS, network.N_SEGMENTS)
        b_results = engine.replay_baseline(self.events_a, baseline_state)
        a_results = engine.replay_aulac(self.events_a, aulac_state)
        after = events.checksum(self.events_a)
        self.assertEqual(before, after)  # replay không mutate input
        self.assertEqual(len(b_results), len(self.events_a))
        self.assertEqual(len(a_results), len(self.events_a))

    def test_same_seed_same_report_checksum(self):
        r1 = engine.run_backtest(self.events_by_seed)
        r2 = engine.run_backtest(self.events_by_seed)
        self.assertEqual(r1["checksum"], r2["checksum"])

    def test_failed_seed_reported_not_dropped(self):
        broken = dict(self.events_by_seed)
        broken[99999] = [{"request_id": "bad", "segment_from": 1, "segment_to": 2,
                          "quantity": 1, "days_to_departure": 10}]  # thiếu distance_km => lỗi
        report = engine.run_backtest(broken)
        failed_ids = {f["seed"] for f in report["failed_seeds"]}
        self.assertIn(99999, failed_ids)
        for good_seed in events.SEEDS:
            self.assertIn(good_seed, report["seeds_run"])

    def test_backtest_runs_under_10s_per_seed(self):
        import time
        t0 = time.time()
        engine.run_seed(self.events_a)
        self.assertLess(time.time() - t0, 10.0)


class TestNoGroundTruth(unittest.TestCase):
    def test_no_ground_truth_import(self):
        """CI gate — Master Plan §2.1 / §9 DoD: grep -r "_ground_truth" src/ phải rỗng."""
        hits = []
        for path in (REPO_ROOT / "src").rglob("*.py"):
            if "_ground_truth" in path.read_text(encoding="utf-8"):
                hits.append(str(path))
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()

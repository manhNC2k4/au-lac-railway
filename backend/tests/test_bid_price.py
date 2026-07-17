# -*- coding: utf-8 -*-
"""DoD tests — DEV2_BE_DATA_FORECAST_BACKTEST.md §Test bắt buộc (bid-price phần).
Run: python -m unittest tests.test_bid_price -v   (từ backend/)
"""
import math
import unittest

from src.forecast import bid_price


class TestBidPrice(unittest.TestCase):
    def test_bid_low_pressure_below_bottleneck(self):
        low = bid_price.bid_price_segment(forecast_remaining=2, remaining_capacity=100, distance_km=200)
        bottleneck = bid_price.bid_price_segment(forecast_remaining=95, remaining_capacity=100, distance_km=200)
        self.assertLess(low, bottleneck)
        self.assertEqual(low, 0)  # pressure=0.02 < p_low=0.5 -> scarcity=0 -> bid=0

    def test_bid_no_nan_no_negative(self):
        cases = [(0, 1, 100), (1000, 1, 1000), (0, 0, 0), (50, 50, 900)]
        for remaining, cap, dist in cases:
            b = bid_price.bid_price_segment(remaining, cap, dist)
            self.assertFalse(math.isnan(b))
            self.assertGreaterEqual(b, 0)
            self.assertIsInstance(b, int)

    def test_round_to_1k(self):
        self.assertEqual(bid_price.round_to_1k(1499), 1000)
        self.assertEqual(bid_price.round_to_1k(1500), 2000)
        self.assertEqual(bid_price.round_to_1k(999_999), 1_000_000)
        self.assertEqual(bid_price.round_to_1k(0), 0)

    def test_scarcity_clipped_0_1(self):
        self.assertEqual(bid_price.scarcity(-5), 0.0)
        self.assertEqual(bid_price.scarcity(5), 1.0)


if __name__ == "__main__":
    unittest.main()

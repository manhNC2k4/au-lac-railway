# -*- coding: utf-8 -*-
"""P0.4 · adapter round-trip — index/seat_id/span/matrix, không cần DB."""
import unittest

import numpy as np

from src.adapters.model_adapter import (cols_to_span, index_seat,
                                         matrix_to_seatmap, seat_index,
                                         seatmap_to_matrix, span_to_cols)
from src.merging.resolver import FREE, SOLD

SEATS = [f"C01-S{n:03d}" for n in range(1, 41)]


def _golden_seatmap() -> dict:
    seats = {s: {str(k): "FREE" for k in range(1, 8)} for s in SEATS}
    seats["C01-S017"] = {"1": "SOLD", "2": "SOLD", "3": "FREE", "4": "FREE",
                         "5": "SOLD", "6": "SOLD", "7": "SOLD"}
    return {"matrix_version": 1, "seats": seats}


class TestAdapter(unittest.TestCase):
    def test_span_cols_roundtrip_golden(self):
        sl = span_to_cols(3, 4)               # THO->DHO
        self.assertEqual((sl.start, sl.stop), (2, 4))
        self.assertEqual(cols_to_span(sl.start, sl.stop), (3, 4))

    def test_seat_index_roundtrip(self):
        i = seat_index(SEATS, "C01-S017")
        self.assertEqual(i, 16)
        self.assertEqual(index_seat(SEATS, i), "C01-S017")

    def test_seatmap_matrix_roundtrip(self):
        seatmap = _golden_seatmap()
        m, ids = seatmap_to_matrix(seatmap, 7)
        self.assertEqual(ids, SEATS)
        i = seat_index(ids, "C01-S017")
        self.assertEqual(list(m[i]), [SOLD, SOLD, FREE, FREE, SOLD, SOLD, SOLD])
        self.assertEqual(matrix_to_seatmap(m, ids)["seats"], seatmap["seats"])

    def test_missing_cell_is_sold_failsafe(self):
        # ô thiếu -> SOLD (không bán nhầm ô chưa rõ)
        m, ids = seatmap_to_matrix({"seats": {"C01-S001": {"3": "FREE"}}}, 7)
        self.assertEqual(list(m[0]), [SOLD, SOLD, FREE, SOLD, SOLD, SOLD, SOLD])


if __name__ == "__main__":
    unittest.main()

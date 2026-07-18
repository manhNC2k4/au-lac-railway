# -*- coding: utf-8 -*-
"""P0.4 · ADAPTER DUY NHẤT giữa quy ước runtime (1-based, inclusive [from,to], seat_id
"C01-S017") và quy ước ma trận của lớp model (0-based, cột nửa mở [a,b), index hàng).

Mục tiêu (kế hoạch §3.4): "cấm convert tay trong route". Mọi chỗ đổi seat_id ⇄ index,
segment span ⇄ cột, seatmap DB ⇄ ma trận int8 phải đi qua đây — một nguồn, có test
round-trip. KHÔNG kéo pandas/DB vào đây; chỉ numpy + dict thuần.

Trạng thái int8 khớp SSM contract: FREE=0, SOLD=1, HELD=2 (dùng lại từ merging.resolver).
"""
from __future__ import annotations

import numpy as np

from ..merging.resolver import FREE, HELD, SOLD

_STATE_CODE = {"FREE": FREE, "SOLD": SOLD, "HELD": HELD}
_CODE_STATE = {v: k for k, v in _STATE_CODE.items()}


# --- segment span (1-based inclusive) ⇄ cột ma trận (0-based nửa mở) -----------
def span_to_cols(seg_from: int, seg_to: int) -> slice:
    """[seg_from, seg_to] 1-based inclusive -> slice cột 0-based nửa mở [from-1, to).
    Golden gap THO->DHO seg[3,4] -> slice(2, 4)."""
    return slice(seg_from - 1, seg_to)


def cols_to_span(col_from: int, col_to: int) -> tuple[int, int]:
    """Nghịch của span_to_cols: [col_from, col_to) 0-based -> (seg_from, seg_to) 1-based inclusive."""
    return col_from + 1, col_to


# --- seat_id ⇄ index hàng -----------------------------------------------------
def seat_index(seat_ids: list[str], seat_id: str) -> int:
    return seat_ids.index(seat_id)


def index_seat(seat_ids: list[str], idx: int) -> str:
    return seat_ids[idx]


# --- seatmap DB (dict) ⇄ ma trận int8 ----------------------------------------
def seatmap_to_matrix(seatmap: dict, n_segments: int) -> tuple[np.ndarray, list[str]]:
    """seatmap {"seats": {seat_id: {"<seg>": "FREE|SOLD|HELD"}}} -> (matrix, seat_ids).
    seat_ids sắp xếp tất định (alphabet). Ô thiếu / trạng thái lạ coi như SOLD (fail-safe:
    không bao giờ bán nhầm ô chưa rõ)."""
    seat_ids = sorted(seatmap["seats"])
    m = np.full((len(seat_ids), n_segments), SOLD, dtype=np.int8)
    for i, sid in enumerate(seat_ids):
        for seg_str, status in seatmap["seats"][sid].items():
            m[i, int(seg_str) - 1] = _STATE_CODE.get(status, SOLD)
    return m, seat_ids


def matrix_to_seatmap(matrix: np.ndarray, seat_ids: list[str]) -> dict:
    """Nghịch của seatmap_to_matrix (không mang matrix_version — chỉ phần 'seats')."""
    seats: dict[str, dict] = {}
    for i, sid in enumerate(seat_ids):
        seats[sid] = {str(c + 1): _CODE_STATE[int(matrix[i, c])] for c in range(matrix.shape[1])}
    return {"seats": seats}


def _demo() -> None:
    """Self-check round-trip (ponytail: chạy `python -m src.adapters.model_adapter`)."""
    # span round-trip, gồm golden gap [3,4] ⇄ [2,4)
    sl = span_to_cols(3, 4)
    assert (sl.start, sl.stop) == (2, 4), sl
    assert cols_to_span(sl.start, sl.stop) == (3, 4)
    # seatmap round-trip
    seat_ids = [f"C01-S{n:03d}" for n in range(1, 41)]
    seatmap = {"matrix_version": 1, "seats": {
        s: {str(k): "FREE" for k in range(1, 8)} for s in seat_ids}}
    # golden gap: C01-S017 SOLD L1-2, FREE L3-4, SOLD L5-7
    seatmap["seats"]["C01-S017"] = {"1": "SOLD", "2": "SOLD", "3": "FREE",
                                     "4": "FREE", "5": "SOLD", "6": "SOLD", "7": "SOLD"}
    m, ids = seatmap_to_matrix(seatmap, 7)
    assert ids == seat_ids
    i = seat_index(ids, "C01-S017")
    assert index_seat(ids, i) == "C01-S017"
    assert list(m[i]) == [SOLD, SOLD, FREE, FREE, SOLD, SOLD, SOLD]
    back = matrix_to_seatmap(m, ids)["seats"]
    assert back == seatmap["seats"], "seatmap round-trip lệch"
    print("model_adapter self-check OK")


if __name__ == "__main__":
    _demo()

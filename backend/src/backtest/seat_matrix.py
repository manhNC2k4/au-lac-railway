# -*- coding: utf-8 -*-
"""Seat x segment matrix — bản OFFLINE/nhẹ dùng riêng cho backtest replay.

KHÔNG phải SSM sản xuất (đó là của BE1, đọc/ghi Postgres, dùng cho API thật).
Backtest cần replay hàng ngàn request nhanh trong bộ nhớ nên có state riêng —
cùng semantics (TRONG/DA_BAN, first-fit nguyên tử) với
`demo/ssm/ssm_contract.py` để hai bên không lệch định nghĩa, nhưng không phụ
thuộc pandas/CSV của dataset thật.

Trạng thái ô: 0 = TRONG (trống) | 1 = DA_BAN (đã bán). Backtest không mô phỏng
hold/expiry (không cần cho so sánh baseline vs Âu Lạc), chỉ BUY/RELEASE.
"""
import numpy as np

TRONG, DA_BAN = 0, 1


class SegmentSeatMatrix:
    """n_seats ghế x n_segments đoạn, segment_id ngoài API là 1-based (L1..Ln)."""

    def __init__(self, n_seats: int, n_segments: int):
        self.n_seats = n_seats
        self.n_segments = n_segments
        self._m = np.full((n_seats, n_segments), TRONG, dtype=np.int8)

    def _cols(self, segment_from: int, segment_to: int) -> tuple[int, int]:
        """segment_from..segment_to (1-based, bao gồm hai đầu) -> slice [a:b) 0-based."""
        return segment_from - 1, segment_to

    def first_fit(self, segment_from: int, segment_to: int) -> int | None:
        """Ghế đầu tiên trống suốt dải; gán DA_BAN nguyên tử và trả seat_idx, None nếu hết."""
        a, b = self._cols(segment_from, segment_to)
        free = (self._m[:, a:b] == TRONG).all(axis=1)
        if not free.any():
            return None
        idx = int(np.argmax(free))
        self._m[idx, a:b] = DA_BAN
        return idx

    def release(self, seat_idx: int, segment_from: int, segment_to: int) -> None:
        a, b = self._cols(segment_from, segment_to)
        self._m[seat_idx, a:b] = TRONG

    def remaining_capacity(self, segment_id: int) -> int:
        return int((self._m[:, segment_id - 1] == TRONG).sum())

    def load_factor(self) -> np.ndarray:
        return (self._m != TRONG).sum(axis=0) / max(self.n_seats, 1)

    def copy(self) -> "SegmentSeatMatrix":
        clone = SegmentSeatMatrix(self.n_seats, self.n_segments)
        clone._m = self._m.copy()
        return clone

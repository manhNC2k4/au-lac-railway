# -*- coding: utf-8 -*-
"""REFERENCE cho owner BE3 — mở rộng merging/resolver.py: GHÉP NHIỀU GHẾ + đổi chỗ.

Viết theo ĐÚNG convention dev (backend/src/merging/resolver.py):
  * matrix (n_seats, n_segments) int8, FREE=0 / SOLD=1 / HELD=2
  * segment_id 1-based, span [seg_from, seg_to] INCLUSIVE, cột 0-based = seg-1
  * read-only trên matrix (BE1 single writer), tất định (tie-break seat_id)
  * seat_id dạng "C01-S017"

Bổ sung so với MVP (dev đang scope-out ghép nhiều ghế — Master §G09/P2):
  - khi KHÔNG có ghế same-seat liên tục, thử phủ [seg_from, seg_to] bằng ≥2 ghế
    (min-interval cover tham lam), tạo option `requires_seat_change=True`;
  - CHỈ đặt điểm đổi tại ga có dwell >= min_dwell_min;
  - cùng seat_class (bản chất: cùng ma trận 1 lớp chỗ);
  - LOẠI TRỪ hành khách ưu tiên (cao tuổi/khuyết tật/trẻ đi một mình/cần hỗ trợ);
  - `requires_customer_consent=True` — API phải hiển thị disclosure & chờ đồng ý.

Đây là ĐỀ XUẤT read-only; gán thật vẫn qua POST /holds CAS của BE1 (mỗi leg 1 cell-set,
tất cả-hoặc-không trong 1 transaction). Trả cấu trúc mở rộng `MergedSeatPlan` — dev cần
thêm schema tương ứng (xem NOTE_DEV.md §resolver).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

FREE, SOLD, HELD = 0, 1, 2
DEFAULT_MIN_DWELL_MIN = 5


@dataclass(frozen=True)
class SeatLeg:
    seat_id: str
    segment_from: int          # 1-based inclusive
    segment_to: int            # 1-based inclusive


@dataclass(frozen=True)
class MergedSeatPlan:
    """Phương án ghép nhiều ghế. requires_seat_change=True luôn (dùng khi hết ghế đơn)."""
    legs: list[SeatLeg]
    change_station_ids: list[str]      # ga đổi (biên giữa các leg)
    so_lan_doi_cho: int                # = len(legs) - 1
    requires_seat_change: bool = True
    requires_customer_consent: bool = True
    dwell_ok: bool = True
    same_class: bool = True

    def to_dict(self):
        return {
            "type": "GHEP_NHIEU_GHE",
            "legs": [{"seat_id": l.seat_id, "segment_from": l.segment_from,
                      "segment_to": l.segment_to} for l in self.legs],
            "change_station_ids": self.change_station_ids,
            "so_lan_doi_cho": self.so_lan_doi_cho,
            "requires_seat_change": self.requires_seat_change,
            "requires_customer_consent": self.requires_customer_consent,
            "dwell_ok": self.dwell_ok, "same_class": self.same_class,
        }


def _cols(seg_from: int, seg_to: int) -> slice:
    return slice(seg_from - 1, seg_to)        # inclusive -> 0-based half-open


def _greedy_cover(matrix: np.ndarray, seg_from: int, seg_to: int,
                  forbidden_change_cols: set[int]) -> list[tuple[int, int, int]] | None:
    """Phủ [seg_from, seg_to] (1-based inclusive) bằng ít ghế nhất, KHÔNG đặt điểm đổi
    tại cột cấm (dwell ngắn). Trả list (seat_row, seg_from_i, seg_to_i) 1-based, hoặc None."""
    a0, b0 = seg_from - 1, seg_to            # cột 0-based: phủ [a0, b0)
    pieces, pos, guard = [], a0, 0
    while pos < b0 and guard <= (b0 - a0):
        guard += 1
        col_free = matrix[:, pos] == FREE
        if not col_free.any():
            return None
        best_s, best_end = -1, pos
        for s in np.flatnonzero(col_free):
            run = pos
            while run < b0 and matrix[s, run] == FREE:
                run += 1
            end = run
            # điểm đổi (cột `end`, tức ga index `end`) không được là ga dwell ngắn
            while a0 < end < b0 and end in forbidden_change_cols:
                end -= 1
            if end > best_end:
                best_s, best_end = int(s), end
            if run >= b0:
                best_s, best_end = int(s), b0
                break
        if best_end <= pos:
            return None
        pieces.append((best_s, pos + 1, best_end))   # -> 1-based inclusive [pos+1, best_end]
        pos = best_end
    if pos < b0 or len(pieces) < 2:
        return None
    return pieces


def resolve_multiseat_options(
    matrix: np.ndarray, seat_ids: list[str], station_ids: list[str],
    seg_from: int, seg_to: int, *,
    priority_passenger: bool = False,
    dwell_minutes: dict[str, float] | None = None,
    min_dwell_min: float = DEFAULT_MIN_DWELL_MIN,
    max_options: int = 3,
) -> list[MergedSeatPlan]:
    """Chỉ trả phương án GHÉP NHIỀU GHẾ (gọi SAU khi resolver same-seat rỗng).
    station_ids: danh sách ga theo thứ tự (len = n_segments+1), station_ids[k] là ga
    đầu của segment k+1; điểm đổi giữa leg tại station_ids[seg_to_i] (0-based index).
    """
    # nhóm ưu tiên: không bao giờ nhận đổi chỗ (YC4) -> rỗng
    if priority_passenger:
        return []
    n_seg = matrix.shape[1]
    dwell = dwell_minutes or {}
    # cột "cấm đặt điểm đổi": ga nội bộ (giữa seg_from..seg_to) có dwell < min
    forbidden = set()
    for col in range(seg_from, seg_to):        # ga index (0-based) = col; giữa span
        ga = station_ids[col] if col < len(station_ids) else None
        if ga is not None and dwell.get(ga, 999) < min_dwell_min:
            forbidden.add(col)
    pieces = _greedy_cover(matrix, seg_from, seg_to, forbidden)
    if not pieces:
        return []
    legs = [SeatLeg(seat_ids[s], a, b) for s, a, b in pieces]
    change_cols = [b for (_, _, b) in pieces[:-1]]      # 1-based seg_to của mỗi leg trừ leg cuối
    change_stations = [station_ids[c] for c in change_cols if c < len(station_ids)]
    dwell_ok = all(dwell.get(g, 999) >= min_dwell_min for g in change_stations)
    plan = MergedSeatPlan(
        legs=legs, change_station_ids=change_stations,
        so_lan_doi_cho=len(legs) - 1, dwell_ok=dwell_ok, same_class=True)
    return [plan][:max_options]

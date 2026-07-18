# -*- coding: utf-8 -*-
"""BE3 · merging/safety resolver — tìm ghế same-seat liên tục cho một O-D span.

Read-only trên matrix (BE1 là single writer — ghi thẳng vào state = bug, DEV3 §Bạn sở hữu).
Matrix: (n_seats, n_segments) int8, 1-based segment_id ánh xạ cột `segment_id-1`,
span [seg_from, seg_to] INCLUSIVE (Master §Golden). Trạng thái khớp SSM contract:
FREE=0 (TRONG), SOLD=1 (DA_BAN), HELD=2 (DANG_GIU).

Cốt lõi là numpy 1 dòng (DEV3 §Resolver — nhỏ hơn bạn nghĩ). KHÔNG di chuyển vé SOLD
(G09, P2 ngoài scope). `reused_gap` chỉ là LABEL, không phải cơ chế (G02).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FREE, SOLD, HELD = 0, 1, 2


@dataclass(frozen=True)
class SeatPlan:
    seat_id: str
    segment_from: int          # 1-based, inclusive
    segment_to: int            # 1-based, inclusive
    reused_gap: bool           # ghế có booking TRƯỚC origin hoặc SAU destination
    requires_seat_change: bool  # luôn False ở MVP (chỉ same-seat liên tục)


def _cols(seg_from: int, seg_to: int) -> slice:
    return slice(seg_from - 1, seg_to)  # inclusive [seg_from, seg_to] -> cột 0-based


def continuous_same_seat(matrix: np.ndarray, seg_from: int, seg_to: int) -> np.ndarray:
    """Chỉ số các ghế FREE trên TOÀN BỘ [seg_from, seg_to]. numpy, < 200ms cho 40×7."""
    free = (matrix[:, _cols(seg_from, seg_to)] == FREE).all(axis=1)
    return np.flatnonzero(free)


def _is_reused_gap(row: np.ndarray, seg_from: int, seg_to: int) -> bool:
    before = row[: seg_from - 1]
    after = row[seg_to:]
    return bool((before == SOLD).any() or (after == SOLD).any())


def resolve_same_seat_options(
    matrix: np.ndarray, seat_ids: list[str], seg_from: int, seg_to: int,
    *, priority_passenger: bool = False,
) -> list[SeatPlan]:
    """Trả danh sách SeatPlan same-seat, đã rank. Không option nào `requires_seat_change`
    (MVP chỉ ghép same-seat liên tục) ⇒ hành khách ưu tiên (so_lan_doi_cho=0) luôn hợp lệ.

    Ranking BEST-FIT: ghế còn ÍT ô FREE thừa ngoài span nhất đứng trước — nhét khách
    vào khoảng trống khít nhất (golden gap C01-S017 = 0 ô thừa), giữ ghế trống dài
    cho chặng dài. reused_gap-first là hệ quả (ghế reused luôn ít ô thừa hơn ghế
    trống hoàn toàn). Tie-break theo seat_id (tất định).
    """
    idxs = continuous_same_seat(matrix, seg_from, seg_to)
    plans = []
    leftover: dict[str, int] = {}
    for i in idxs:
        row = matrix[i]
        plans.append(SeatPlan(
            seat_id=seat_ids[i], segment_from=seg_from, segment_to=seg_to,
            reused_gap=_is_reused_gap(row, seg_from, seg_to),
            requires_seat_change=False,
        ))
        leftover[seat_ids[i]] = int((row[: seg_from - 1] == FREE).sum()
                                    + (row[seg_to:] == FREE).sum())
    # priority_passenger: chỉ nhận same-seat, không bao giờ requires_seat_change (DEV3 §3).
    # Ở MVP mọi option đã là same-seat nên filter là no-op — nhưng giữ để invariant hiện rõ.
    if priority_passenger:
        plans = [p for p in plans if not p.requires_seat_change]
    plans.sort(key=lambda p: (leftover[p.seat_id], p.seat_id))
    return plans


def best_same_seat(matrix: np.ndarray, seat_ids: list[str], seg_from: int, seg_to: int,
                   *, priority_passenger: bool = False) -> SeatPlan | None:
    opts = resolve_same_seat_options(matrix, seat_ids, seg_from, seg_to,
                                     priority_passenger=priority_passenger)
    return opts[0] if opts else None


# ----------------------------------------------------------------------------
# P5 · GHÉP NHIỀU GHẾ (đổi chỗ) — port từ integration/resolver_multiseat.py.
# Gọi SAU khi resolve_same_seat_options rỗng: phủ [seg_from,seg_to] bằng ≥2 ghế
# (min-interval cover tham lam). Điểm đổi chỉ đặt tại ga có dwell >= min_dwell.
# Loại trừ hành khách ưu tiên (YC4). Read-only; gán thật vẫn qua CAS /holds.
# ----------------------------------------------------------------------------
DEFAULT_MIN_DWELL_MIN = 5   # nguồn: tham số chính sách dwell 5' (kế hoạch §1 "số KHÔNG phải fake")


@dataclass(frozen=True)
class SeatLeg:
    seat_id: str
    segment_from: int          # 1-based, inclusive
    segment_to: int            # 1-based, inclusive


@dataclass(frozen=True)
class MergedSeatPlan:
    """Phương án ghép nhiều ghế; requires_seat_change=True luôn (dùng khi hết ghế đơn)."""
    legs: list[SeatLeg]
    change_station_ids: list[str]      # ga đổi (biên giữa các leg)
    so_lan_doi_cho: int                # = len(legs) - 1
    requires_seat_change: bool = True
    requires_customer_consent: bool = True
    dwell_ok: bool = True
    same_class: bool = True

    def to_dict(self) -> dict:
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
    """Chỉ trả phương án GHÉP NHIỀU GHẾ (gọi SAU khi resolve_same_seat_options rỗng).
    station_ids: danh sách ga theo thứ tự (len = n_segments+1); điểm đổi giữa leg tại
    station_ids[seg_to_i] (0-based). Nhóm ưu tiên -> rỗng (không bao giờ đổi chỗ, YC4)."""
    if priority_passenger:
        return []
    dwell = dwell_minutes or {}
    # cột "cấm đặt điểm đổi": ga nội bộ (giữa seg_from..seg_to) có dwell < min
    forbidden = set()
    for col in range(seg_from, seg_to):        # ga index (0-based) = col; giữa span
        ga = station_ids[col] if col < len(station_ids) else None
        if ga is not None and dwell.get(ga, 999) < min_dwell_min:  # nguồn: 999'=sentinel thiếu dữ liệu dwell
            forbidden.add(col)
    pieces = _greedy_cover(matrix, seg_from, seg_to, forbidden)
    if not pieces:
        return []
    legs = [SeatLeg(seat_ids[s], a, b) for s, a, b in pieces]
    change_cols = [b for (_, _, b) in pieces[:-1]]      # 1-based seg_to mỗi leg trừ leg cuối
    change_stations = [station_ids[c] for c in change_cols if c < len(station_ids)]
    dwell_ok = all(dwell.get(g, 999) >= min_dwell_min for g in change_stations)  # nguồn: 999'=sentinel
    plan = MergedSeatPlan(
        legs=legs, change_station_ids=change_stations,
        so_lan_doi_cho=len(legs) - 1, dwell_ok=dwell_ok, same_class=True)
    return [plan][:max_options]


def best_multiseat(matrix: np.ndarray, seat_ids: list[str], station_ids: list[str],
                   seg_from: int, seg_to: int, **kw) -> MergedSeatPlan | None:
    opts = resolve_multiseat_options(matrix, seat_ids, station_ids, seg_from, seg_to, **kw)
    return opts[0] if opts else None

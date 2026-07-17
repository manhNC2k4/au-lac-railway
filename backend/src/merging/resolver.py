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

    Ranking: ưu tiên ghế TÁI DÙNG KHOẢNG TRỐNG (reused_gap) trước — đây là mục tiêu
    ghép chặng: nhồi khách vào ghế đã bán một phần, giữ ghế trống-hoàn-toàn cho chặng dài.
    Sau đó theo thứ tự seat_id (tất định).
    """
    idxs = continuous_same_seat(matrix, seg_from, seg_to)
    plans = [
        SeatPlan(
            seat_id=seat_ids[i], segment_from=seg_from, segment_to=seg_to,
            reused_gap=_is_reused_gap(matrix[i], seg_from, seg_to),
            requires_seat_change=False,
        )
        for i in idxs
    ]
    # priority_passenger: chỉ nhận same-seat, không bao giờ requires_seat_change (DEV3 §3).
    # Ở MVP mọi option đã là same-seat nên filter là no-op — nhưng giữ để invariant hiện rõ.
    if priority_passenger:
        plans = [p for p in plans if not p.requires_seat_change]
    plans.sort(key=lambda p: (not p.reused_gap, p.seat_id))
    return plans


def best_same_seat(matrix: np.ndarray, seat_ids: list[str], seg_from: int, seg_to: int,
                   *, priority_passenger: bool = False) -> SeatPlan | None:
    opts = resolve_same_seat_options(matrix, seat_ids, seg_from, seg_to,
                                     priority_passenger=priority_passenger)
    return opts[0] if opts else None

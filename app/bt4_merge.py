# -*- coding: utf-8 -*-
"""C3 / BÀI TOÁN CON 4 — Segment Merging (ghép khoảng trống) với đủ ràng buộc YC4.

Input : SSM (BT2) + yêu cầu (chuyến, O, D, loại_ghế, hồ_sơ_khách).
Output: SeatOption[] xếp hạng:
  1. xuyen_suot — 1 ghế trống suốt (không merge)
  2. gap_khit  — ghế lấp khít khoảng trống giữa 2 vé đã bán
  3. ghep_nhieu — ghép ≥2 ghế, CHỈ khi bất khả kháng (hết ghế đơn), và:
       * ga đổi phải có dwell >= MIN_DWELL_PHUT (đủ thời gian đổi chỗ)
       * cùng lớp chỗ vật lý (cùng ma trận lớp — cung_hang_cho=True)
       * can_khach_chap_nhan=True — backend PHẢI hiện disclosure & chờ khách đồng ý
       * LOẠI TRỪ với hồ sơ ưu tiên (cao tuổi / khuyết tật / trẻ một mình / cần hỗ trợ)
Thuần đề xuất — KHÔNG mutate kho; gán thật ở bước confirm của backend.
"""
import numpy as np

from app.config import MACRO_CLASS, MIN_DWELL_PHUT, TRONG
from app.contracts import PassengerProfile, ProposalLog, SeatOption, SeatSegment


def _ga_at(ssm, chuyen_id, local_seg_idx):
    lo, _ = ssm._span[chuyen_id]
    return ssm.st.ga_id[lo + local_seg_idx]


def _dwell_at(ssm, chuyen_id, local_seg_idx) -> int:
    lo, _ = ssm._span[chuyen_id]
    return int(ssm.st.dwell_phut[lo + local_seg_idx]) if "dwell_phut" in ssm.st else 99


def _seg(ssm, cid, s, x, y) -> SeatSegment:
    return SeatSegment(seat_idx=int(s), seg_from=int(x), seg_to=int(y),
                       ga_di=_ga_at(ssm, cid, x), ga_den=_ga_at(ssm, cid, y))


def _greedy_cover(m: np.ndarray, a: int, b: int, forbidden_change: set[int]):
    """Min-interval-cover tham lam, KHÔNG đặt điểm đổi tại đoạn cấm (dwell ngắn).
    Trả list (seat, x, y) phủ [a,b) hoặc None."""
    pieces, pos, guard = [], a, 0
    while pos < b and guard <= (b - a):
        guard += 1
        col = m[:, pos] == TRONG
        if not col.any():
            return None
        best_s, best_end = -1, pos
        for s in np.flatnonzero(col):
            run = pos
            while run < b and m[s, run] == TRONG:
                run += 1
            # điểm đổi (run) không được rơi vào ga dwell ngắn — lùi về ga hợp lệ gần nhất
            end = run
            while end < b and end in forbidden_change:
                end -= 1
            if end > best_end:
                best_s, best_end = int(s), end
            if run >= b:
                best_s, best_end = int(s), min(run, b)
                break
        if best_end <= pos:
            return None
        pieces.append((best_s, pos, best_end))
        pos = best_end
    return pieces if pos >= b else None


def find_options(ssm, chuyen_id: str, loai_ghe: str, ga_di: str, ga_den: str,
                 profile: PassengerProfile | bool = False, max_options: int = 6) -> dict:
    # backward-compat: cho phép truyền bool uu_tien thay vì PassengerProfile
    if isinstance(profile, PassengerProfile):
        uu_tien = profile.thuoc_nhom_uu_tien
    else:
        uu_tien = bool(profile)
        profile = PassengerProfile(cao_tuoi=uu_tien)

    cls = MACRO_CLASS.get(loai_ghe, loai_ghe)
    a, b = ssm.seg_range(chuyen_id, ga_di, ga_den)
    m = ssm.get_state(chuyen_id, cls)             # bản sao — không mutate kho
    n_seg = m.shape[1]
    options: list[SeatOption] = []

    # ga cấm đặt điểm đổi chỗ: dwell < MIN_DWELL (đoạn nội bộ (a,b))
    forbidden = {e for e in range(a + 1, b) if _dwell_at(ssm, chuyen_id, e) < MIN_DWELL_PHUT}

    free_full = (m[:, a:b] == TRONG).all(axis=1)
    pristine, gapfill = [], []
    for s in np.flatnonzero(free_full):
        row_free = (m[s] == TRONG)
        if row_free.all():
            pristine.append(int(s))
        else:
            margin_l = a - (np.max(np.flatnonzero(~row_free[:a])) + 1) if (~row_free[:a]).any() else a
            margin_r = (np.min(np.flatnonzero(~row_free[b:])) if (~row_free[b:]).any() else n_seg - b)
            gapfill.append((int(s), int(margin_l + margin_r)))

    # 1) xuyên suốt
    if pristine:
        options.append(SeatOption(loai="xuyen_suot", seat_class=cls,
                                  ghe_theo_doan=[_seg(ssm, chuyen_id, pristine[0], a, b)],
                                  ghi_chu=f"{len(pristine)} ghế pristine khả dụng"))
    # 2) lấp gap khít nhất
    for s, khit in sorted(gapfill, key=lambda t: t[1])[:2]:
        options.append(SeatOption(loai="gap_khit", seat_class=cls,
                                  ghe_theo_doan=[_seg(ssm, chuyen_id, s, a, b)],
                                  do_khit=khit, ghi_chu=f"lấp gap, biên trống thừa={khit} đoạn"))
    # 3) ghép nhiều ghế — CHỈ khi bất khả kháng & khách không thuộc nhóm loại trừ
    if not uu_tien and not (pristine or gapfill):
        pieces = _greedy_cover(m, a, b, forbidden)
        if pieces and len(pieces) >= 2:
            ga_doi = [_ga_at(ssm, chuyen_id, x) for (_, x, _) in pieces[1:]]
            dwell_ok = all(_dwell_at(ssm, chuyen_id, x) >= MIN_DWELL_PHUT
                           for (_, x, _) in pieces[1:])
            if dwell_ok:
                options.append(SeatOption(
                    loai="ghep_nhieu", seat_class=cls,
                    ghe_theo_doan=[_seg(ssm, chuyen_id, s, x, y) for s, x, y in pieces],
                    so_lan_doi_cho=len(pieces) - 1, ga_doi=ga_doi,
                    can_doi_cho=True, can_khach_chap_nhan=True,
                    dwell_du=True, cung_hang_cho=True,
                    ghi_chu=(f"bất khả kháng: hết ghế đơn; đổi chỗ {len(pieces)-1} lần tại "
                             f"{', '.join(ga_doi)} (dwell ≥{MIN_DWELL_PHUT}p); "
                             f"CẦN khách chủ động đồng ý")))

    for i, o in enumerate(options[:max_options], 1):
        o.rank = i
    kha_thi = bool(options)
    ly_do = None if kha_thi else (
        "hết chỗ; phương án ghép bị loại vì khách thuộc nhóm ưu tiên" if uu_tien
        else "hết chỗ trên hành trình (kể cả ghép)")
    out = {"chuyen_id": chuyen_id, "ga_di": ga_di, "ga_den": ga_den, "seat_class": cls,
           "uu_tien": uu_tien, "kha_thi": kha_thi, "ly_do": ly_do,
           "phuong_an": [o.to_dict() for o in options[:max_options]]}
    out["_log"] = ProposalLog(
        loai="MERGE", input={"chuyen_id": chuyen_id, "od": [ga_di, ga_den],
                             "cls": cls, "profile": profile.to_dict()},
        output={"kha_thi": kha_thi, "n_options": len(options),
                "co_ghep": any(o.loai == "ghep_nhieu" for o in options)},
        explain=ly_do or f"{len(options)} phương án, tốt nhất: {options[0].loai}").to_dict()
    return out


def list_mergeable_gaps(ssm, chuyen_id: str) -> list[dict]:
    """Danh sách khoảng trống có thể ghép (mergeable-gap list — output tối thiểu đề bài)."""
    from app.config import SEAT_CLASSES
    gaps = []
    seg_meta = ssm.get_segment_meta(chuyen_id)
    for cls in SEAT_CLASSES:
        m = ssm.get_state(chuyen_id, cls)
        used = ~(m == TRONG).all(axis=1)
        for s in np.flatnonzero(used):
            row = m[s] == TRONG
            e = 0
            while e < len(row):
                if row[e]:
                    start = e
                    while e < len(row) and row[e]:
                        e += 1
                    if start > 0 or e < len(row):     # gap thật (không phải ghế trống hoàn toàn)
                        gaps.append(dict(seat_class=cls, seat_idx=int(s),
                                         seg_from=start, seg_to=e,
                                         ga_di=seg_meta.ga_dau[start], ga_den=seg_meta.ga_cuoi[e - 1],
                                         so_doan=e - start))
                else:
                    e += 1
    return gaps

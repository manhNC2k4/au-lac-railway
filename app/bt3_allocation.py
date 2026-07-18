# -*- coding: utf-8 -*-
"""C1 / BÀI TOÁN CON 3 — Segment Load Analysis + Inventory Allocation (segment-splitting).

Input : Seat State Matrix (BT2) + bảng dự báo cầu còn lại (BT1).
Output (contracts):
  - SegmentLoad[]  : LF từng khu gian + phân loại nghẽn/trống + bid price
  - QuotaRow[]     : hạn mức (đoạn, loại_hành_trình, lớp_chỗ) + booking limit
  - bid_price      : dual sức chứa theo (lớp_chỗ, đoạn) — chi phí cơ hội 1 chỗ/đoạn,
                     là "chi phí biên" cho BT5 định giá tối ưu doanh thu.

DLP mỗi LỚP CHỖ: max Σ f·y  s.t.  A y ≤ chỗ_còn_lại,  0 ≤ y ≤ D_còn_lại.
Ma trận phủ đoạn liên tiếp => tổng đơn modular (doc 02 §1.2) => nghiệm LP nguyên.
Protection level chặng dài = phần cầu dài được LP chấp nhận; booking limit chặng
ngắn trên đoạn nghẽn = chỗ trống − phần bảo vệ cho hành trình dài đi qua đoạn đó.
"""
import numpy as np
import pandas as pd

try:
    from scipy.optimize import linprog
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from app.config import (BAND_EDGES, BAND_LABELS, BOTTLENECK_LF, SEAT_CLASSES,
                        SLACK_LF, TRONG, mac_tau_of)
from app.contracts import ProposalLog, QuotaRow, SegmentLoad

# map nhãn seat_class của BT1 (NGOI/K6/K4) -> macro class của SSM
FC_CLASS = {"NGOI": "NGOI_MEM_DH", "K6": "NAM_K6", "K4": "NAM_K4"}


def band_of(d_km: float) -> str:
    for i in range(len(BAND_LABELS)):
        if d_km <= BAND_EDGES[i + 1]:
            return BAND_LABELS[i]
    return BAND_LABELS[-1]


def _remaining_by_class(ssm, chuyen_id):
    """(dict cls -> vector chỗ trống theo đoạn, tổng sức chứa, occ tổng)."""
    lo, hi = ssm._span[chuyen_id]
    n_seg = hi - lo
    rem, occ_tot, cap_tot = {}, np.zeros(n_seg), 0
    for c in SEAT_CLASSES:
        m = ssm.get_state(chuyen_id, c)
        occ = (m != TRONG).sum(axis=0)
        rem[c] = np.maximum(m.shape[0] - occ, 0).astype(float)
        occ_tot += occ
        cap_tot += m.shape[0]
    return rem, cap_tot, occ_tot, n_seg


def _od_candidates(ssm, pricer, chuyen_id, forecast, cls, remaining_cls):
    """Danh sách O–D + cầu (UB) + giá tham chiếu cho DLP một lớp chỗ.

    co_du_bao=False khi không có forecast: DLP vẫn chạy để ước quota cấu trúc
    (UB = chỗ trống) nhưng bid price khi đó VÔ NGHĨA về khan hiếm => caller phải
    zero-out (không có dự báo = không có thông tin khan hiếm, không được ép giá)."""
    lo, hi = ssm._span[chuyen_id]
    mac_tau = mac_tau_of(chuyen_id)
    tier0 = {"NGOI_MEM_DH": "NGOI_MEM_DH", "NAM_K6": "NAM_K6_T2", "NAM_K4": "NAM_K4_T1"}[cls]
    fc_lookup = {}
    if forecast is not None and len(forecast):
        f = forecast[forecast.seat_class.map(FC_CLASS).fillna(forecast.seat_class) == cls] \
            if "seat_class" in forecast else forecast
        col = "remaining_demand" if "remaining_demand" in f else "forecast_demand"
        fc_lookup = f.groupby(["origin", "dest"])[col].sum().to_dict()
    co_du_bao = bool(fc_lookup)
    ods, ub, fares, bands = [], [], [], []
    stops = list(range(lo, hi + 1))
    for ii in range(len(stops) - 1):
        for jj in range(ii + 1, len(stops)):
            gi, gj = stops[ii], stops[jj]
            ga_i, ga_j = ssm.st.ga_id[gi], ssm.st.ga_id[gj]
            d_km = abs(ssm.st.ly_trinh_km[gj] - ssm.st.ly_trinh_km[gi])
            if d_km < 30:
                continue
            dem = fc_lookup.get((ga_i, ga_j))
            if dem is None:
                dem = float(remaining_cls[ii:jj].min()) if not co_du_bao else 0.0
            ods.append((ii, jj))
            ub.append(max(float(dem), 0.0))
            fares.append(pricer.f0(mac_tau, ga_i, ga_j, tier0))
            bands.append(band_of(d_km))
    return ods, ub, fares, bands, co_du_bao


def _solve_dlp(n_seg, ods, ub, fares, remaining):
    """(y*, bid_price[], z_opt) cho 1 lớp chỗ."""
    if not HAS_SCIPY or not ods:
        return np.zeros(len(ods)), np.zeros(n_seg), 0.0
    A = np.zeros((n_seg, len(ods)))
    for k, (i, j) in enumerate(ods):
        A[i:j, k] = 1.0
    res = linprog(c=-np.asarray(fares, float), A_ub=A, b_ub=remaining,
                  bounds=[(0, u) for u in ub], method="highs")
    if not res.success:
        return np.zeros(len(ods)), np.zeros(n_seg), 0.0
    duals = getattr(getattr(res, "ineqlin", None), "marginals", None)
    bp = -np.asarray(duals) if duals is not None else np.zeros(n_seg)
    return res.x, np.maximum(bp, 0.0), float(-res.fun)


def analyze_run(ssm, pricer, chuyen_id: str, forecast: pd.DataFrame | None = None) -> dict:
    """Phân tích 1 chuyến: SegmentLoad[] + QuotaRow[] + bid price + đoạn nghẽn/trống."""
    seg_meta = ssm.get_segment_meta(chuyen_id)
    rem, cap_tot, occ_tot, n_seg = _remaining_by_class(ssm, chuyen_id)
    lf = occ_tot / max(cap_tot, 1)

    quota_rows: list[QuotaRow] = []
    bid_by_class: dict[str, list] = {}
    z_opt_total = 0.0
    for cls in SEAT_CLASSES:
        ods, ub, fares, bands, co_du_bao = _od_candidates(ssm, pricer, chuyen_id,
                                                          forecast, cls, rem[cls])
        y, bp, z = _solve_dlp(n_seg, ods, ub, fares, rem[cls])
        z_opt_total += z
        if not co_du_bao:
            bp = np.zeros(n_seg)      # không dự báo => không tín hiệu khan hiếm => bid=0
        bid_by_class[cls] = bp.round(0).astype(int).tolist()
        # protection: cầu được chấp nhận theo (đoạn, băng)
        prot = {(e, b): 0.0 for e in range(n_seg) for b in BAND_LABELS}
        for k, (i, j) in enumerate(ods):
            for e in range(i, j):
                prot[(e, bands[k])] += y[k]
        for e in range(n_seg):
            protected_long = prot[(e, "dai")] + prot[(e, "trung")]
            for b in BAND_LABELS:
                q = int(round(prot[(e, b)]))
                # booking limit chặng ngắn = chỗ còn − phần bảo vệ dài/trung (nested)
                if b == "ngan":
                    limit = int(max(rem[cls][e] - round(protected_long), 0))
                else:
                    limit = int(rem[cls][e])
                quota_rows.append(QuotaRow(
                    khu_gian_id=int(seg_meta.khu_gian_id[e]), loai_hanh_trinh=b,
                    seat_class=cls, quota=q, booking_limit=min(q if b == "ngan" else limit, limit)
                    if b == "ngan" else limit, bid_price=int(bp[e])))

    bid_agg = [max(bid_by_class[c][e] for c in SEAT_CLASSES) for e in range(n_seg)]
    seg_loads: list[SegmentLoad] = []
    for e in range(n_seg):
        tag = ("nghen" if lf[e] >= BOTTLENECK_LF
               else "trong" if lf[e] <= SLACK_LF else "binh_thuong")
        seg_loads.append(SegmentLoad(
            khu_gian_id=int(seg_meta.khu_gian_id[e]), ga_dau=seg_meta.ga_dau[e],
            ga_cuoi=seg_meta.ga_cuoi[e], lf=round(float(lf[e]), 4),
            suc_chua=int(cap_tot), con_trong=int(cap_tot - occ_tot[e]),
            phan_loai=tag, bid_price=int(bid_agg[e])))

    out = {
        "chuyen_id": chuyen_id,
        "lf_theo_doan": [s.to_dict() for s in seg_loads],
        "quota": [q.to_dict() for q in quota_rows],
        "bid_price_theo_lop": bid_by_class,
        "doan_nghen": [s.to_dict() for s in seg_loads if s.phan_loai == "nghen"],
        "doan_trong": [s.to_dict() for s in seg_loads if s.phan_loai == "trong"],
        "z_opt_dlp": int(round(z_opt_total)),
        "lf_bq": round(float(lf.mean()), 4),
        "lf_max": round(float(lf.max()), 4),
    }
    out["_log"] = ProposalLog(loai="ALLOCATION", input={"chuyen_id": chuyen_id},
                              output={"z_opt": out["z_opt_dlp"], "n_nghen": len(out["doan_nghen"])},
                              explain=f"DLP 3 lớp chỗ, z_opt={out['z_opt_dlp']:,}đ, "
                                      f"{len(out['doan_nghen'])} đoạn nghẽn").to_dict()
    return out


def load_factor_route(ssm, chuyen_id: str, ga_di: str, ga_den: str,
                      bid_by_class: dict | None = None, seat_class: str | None = None) -> dict:
    """LF + bid price trên các đoạn của hành trình — input trực tiếp cho BT5."""
    seg_meta = ssm.get_segment_meta(chuyen_id)
    lf = ssm.load_factor(chuyen_id)
    a, b = ssm.seg_range(chuyen_id, ga_di, ga_den)
    segs, bp_route = [], 0
    for e in range(a, b):
        bp = 0
        if bid_by_class and seat_class:
            bp = int(bid_by_class.get(seat_class, [0] * len(lf))[e])
        bp_route += bp
        segs.append(dict(khu_gian_id=int(seg_meta.khu_gian_id[e]), ga_dau=seg_meta.ga_dau[e],
                         ga_cuoi=seg_meta.ga_cuoi[e], lf=round(float(lf[e]), 4), bid_price=bp))
    return {"segments": segs, "bid_price_route": int(bp_route)}

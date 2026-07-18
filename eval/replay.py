# -*- coding: utf-8 -*-
"""D1 — Replay engine: phát lại search_log theo thứ tự mua, chạy 2 chính sách.

FCFS (baseline): first-fit ghế đơn xuyên suốt, KHÔNG ghép, giá tĩnh = F0 × mùa vụ.
AI  (hệ thống): ghép chặng (BT4 đủ ràng buộc) + định giá động (BT5, bid-price DLP
               refresh theo sự kiện) + CSXH sau cùng.

Khách quyết định mua bằng WTP THẬT từ _ground_truth/wtp.parquet — CHỈ để chấm
điểm (cho phép theo doc 03), không bao giờ làm feature.
Tất định: cờ ưu tiên & CSXH gán bằng hash yeu_cau_id (cùng seed generator ⇒ ổn định).
"""
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.bt2_ssm import SeatStateMatrix
from app.bt3_allocation import analyze_run, load_factor_route
from app.bt4_merge import find_options
from app.bt5_pricing import Pricer
from app.config import ARTIFACTS, DATA, MACRO_CLASS, SEAT_CLASSES, TIERS
from app.contracts import PassengerProfile

GT = DATA.parent / "_ground_truth"


def load_forecast(date: str) -> pd.DataFrame | None:
    """Bảng hợp đồng BT1 cho ngày này — ưu tiên contract backtest (train-truoc-ngày),
    fallback contract chính (test period ≥ 01/5)."""
    for name in ("forecast_backtest_contract.csv", "forecast_output_contract.csv"):
        p = ARTIFACTS / name
        if p.exists():
            fc = pd.read_csv(p)
            fc = fc[fc.date == date]
            if len(fc):
                return fc
    return None
REFRESH_EVERY = 200            # re-solve DLP sau mỗi N vé bán (event-driven)
CSXH_PROBS = [("KHONG", 0.780, 0.0), ("NGUOI_CAO_TUOI", 0.860, 0.15),
              ("TRE_6_10", 0.900, 0.25), ("HSSV", 0.980, 0.10),
              ("THUONG_BINH_CDHH", 0.995, 0.30), ("ME_VNAH_TIEN_KN", 1.0, 0.90)]


def _frac(*keys) -> float:
    h = hashlib.sha256("|".join(str(k) for k in keys).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2 ** 64


def _csxh(rq_id) -> tuple[str, float]:
    r = _frac(rq_id, "csxh")
    for ten, cum, muc in CSXH_PROBS:
        if r < cum:
            return ten, muc
    return "KHONG", 0.0


def load_day(date: str, mac_tau_filter: list[str] | None):
    month = date[:7]
    sl = pd.read_parquet(str(DATA / "search_log" / f"thang={month}"))
    sl = sl[sl.ngay_di == date].copy()
    if mac_tau_filter:
        sl["mac"] = sl.chuyen_id.str.rsplit("_", n=1).str[0]
        sl = sl[sl.mac.isin(mac_tau_filter)]
    tx = pd.read_parquet(str(DATA / "transactions" / f"thang={month}"),
                         columns=["ve_id", "yeu_cau_id", "loai_cho", "cu_ly_km"])
    wtp = pd.read_parquet(GT / "wtp.parquet")
    sl = sl.merge(wtp, on="yeu_cau_id", how="left")
    tier_map = dict(zip(tx.yeu_cau_id, tx.loai_cho))
    sl["tier"] = sl.yeu_cau_id.map(tier_map)
    # yêu cầu không mua: gán tier tất định
    def pick_tier(rq):
        cls = SEAT_CLASSES[int(_frac(rq, "cls") * 3)]
        ts = TIERS[cls]
        return ts[int(_frac(rq, "tier") * len(ts))]
    na = sl.tier.isna()
    sl.loc[na, "tier"] = [pick_tier(r) for r in sl.loc[na, "yeu_cau_id"]]
    sl = sl.sort_values("lead_time_ngay", ascending=False)   # thứ tự mua thật
    return sl


def _ctx_for(date: str):
    cal = pd.read_csv(DATA / "calendar_events.csv")
    cal = cal[pd.to_numeric(cal.tau_tet, errors="coerce").notna()]
    row = cal[cal.ngay == date].iloc[0]
    return {"tau_tet": int(row.tau_tet), "dow": int(row.dow),
            "la_le": str(row.la_le) == "True", "dot_ban_ve": row.dot_ban_ve,
            "che_do_gia": row.che_do_gia}


def run_policy(date: str, policy: str, mac_tau_filter: list[str] | None = None,
               requests: pd.DataFrame | None = None, verbose: bool = False) -> dict:
    """policy ∈ {'FCFS','AI'} — trả kết quả thô cho metrics.summarize."""
    assert policy in ("FCFS", "AI")
    sl = requests if requests is not None else load_day(date, mac_tau_filter)
    ctx = _ctx_for(date)
    pricer = Pricer.load()
    ssm = SeatStateMatrix()
    fc_all = load_forecast(date) if policy == "AI" else None
    sales, refusals, latency = [], [], []
    alloc_cache: dict[str, dict] = {}
    sold_since_refresh: dict[str, int] = {}
    short_sold: dict = {}          # (cid, seg_local, cls) -> vé ngắn bán từ lần refresh
    km = ssm.st.set_index("ga_id").ly_trinh_km.to_dict()

    def short_limit(cid, cls, e):
        """Booking limit chặng ngắn tại đoạn e (local idx) — CHỈ bind khi đoạn
        thực sự khan hiếm (LF >= 0.75 tại lần refresh gần nhất); đoạn rảnh thì
        vé ngắn là doanh thu thuần, không chặn."""
        alloc = alloc_cache.get(cid)
        if not alloc:
            return None
        if alloc["lf_theo_doan"][e]["lf"] < 0.75:
            return None
        lo, _ = ssm._span[cid]
        kg = lo + e + 1                        # khu_gian_id toàn cục
        for q in alloc["quota"]:
            if q["khu_gian_id"] == kg and q["seat_class"] == cls \
                    and q["loai_hanh_trinh"] == "ngan":
                return q["booking_limit"]
        return None

    for r in sl.itertuples(index=False):
        t0 = time.perf_counter()
        rq, cid, tier = r.yeu_cau_id, r.chuyen_id, r.tier
        cls = MACRO_CLASS[tier]
        try:
            a, b = ssm.seg_range(cid, r.ga_di, r.ga_den)
        except (KeyError, ValueError):
            continue
        uu_tien = _frac(rq, "priority") < 0.09
        profile = PassengerProfile(cao_tuoi=uu_tien)
        _, muc_csxh = _csxh(rq)
        d_km = abs(km[r.ga_den] - km[r.ga_di])
        mac_tau = cid.rsplit("_", 1)[0]
        f0 = pricer.f0(mac_tau, r.ga_di, r.ga_den, tier)

        # ---- giá ----
        if policy == "FCFS":
            dmua, _ = pricer._delta_mua(ctx)
            gia_niem_yet = int(round(min(max(f0 * (1 + dmua), 0.55 * f0), 1.6 * f0)))
        else:
            if cid not in alloc_cache or sold_since_refresh.get(cid, 0) >= REFRESH_EVERY:
                fc_run = None
                if fc_all is not None:
                    fc_run = fc_all[fc_all.train_id == mac_tau]
                alloc_cache[cid] = analyze_run(ssm, pricer, cid, fc_run)
                sold_since_refresh[cid] = 0
                short_sold = {k: v for k, v in short_sold.items() if k[0] != cid}
            # QUOTA GATING: chặng ngắn (<300km) trên đoạn nghẽn bị chặn khi vượt limit
            if d_km < 300:
                blocked_q = False
                for e in range(a, b):
                    lim = short_limit(cid, cls, e)
                    if lim is not None and short_sold.get((cid, e, cls), 0) >= lim:
                        blocked_q = True
                        break
                if blocked_q:
                    refusals.append({"rq": rq, "ly_do": "QUOTA_NGAN"})
                    latency.append((time.perf_counter() - t0) * 1000)
                    continue
            lfr = load_factor_route(ssm, cid, r.ga_di, r.ga_den,
                                    alloc_cache[cid]["bid_price_theo_lop"], cls)
            q = pricer.quote(mac_tau, r.ga_di, r.ga_den, tier,
                             {**ctx, "u": float(r.lead_time_ngay)}, lfr)
            gia_niem_yet = int(round(q.gia_de_xuat))     # chưa CSXH (muc=0 ở đây)
        gia_cuoi = int(round(gia_niem_yet * (1 - muc_csxh)))

        # ---- WTP quyết định ----
        wtp = getattr(r, "wtp", None)
        if wtp is None or pd.isna(wtp):
            wtp = f0 * 1.1
        if wtp < gia_cuoi:
            refusals.append({"rq": rq, "ly_do": "BO_VI_GIA"})
            latency.append((time.perf_counter() - t0) * 1000)
            continue

        # ---- tìm ghế ----
        if policy == "FCFS":
            seat = ssm.first_fit(cid, cls, a, b)
            pieces = [(seat, a, b)] if seat is not None else None
            loai_ghe, n_doi = ("xuyen_suot", 0) if pieces else (None, 0)
        else:
            opts = find_options(ssm, cid, cls, r.ga_di, r.ga_den, profile)
            if opts["kha_thi"]:
                best = opts["phuong_an"][0]
                # khách chấp nhận đổi chỗ? (sigma model xấp xỉ, tất định)
                if best["can_khach_chap_nhan"] and _frac(rq, "accept") > 0.75:
                    refusals.append({"rq": rq, "ly_do": "TU_CHOI_DOI_CHO"})
                    latency.append((time.perf_counter() - t0) * 1000)
                    continue
                pieces = [(p["seat_idx"], p["seg_from"], p["seg_to"])
                          for p in best["ghe_theo_doan"]]
                for s, x, y in pieces:
                    ssm.assign(cid, cls, s, x, y)
                loai_ghe, n_doi = best["loai"], best["so_lan_doi_cho"]
                pieces_assigned = True
            else:
                pieces = None
        if pieces is None:
            refusals.append({"rq": rq, "ly_do": "HET_CHO"})
            latency.append((time.perf_counter() - t0) * 1000)
            continue
        if policy == "FCFS":
            pass  # first_fit đã gán
        sold_since_refresh[cid] = sold_since_refresh.get(cid, 0) + 1
        if policy == "AI" and d_km < 300:
            for e in range(a, b):
                short_sold[(cid, e, cls)] = short_sold.get((cid, e, cls), 0) + 1
        sales.append({"rq": rq, "chuyen_id": cid, "gia": gia_cuoi, "f0": f0,
                      "d_km": d_km, "so_lan_doi_cho": n_doi, "loai_ghe": loai_ghe,
                      "csxh": muc_csxh})
        latency.append((time.perf_counter() - t0) * 1000)

    # ---- tổng hợp trạng thái cuối ----
    fill, n_gaps, cap_km = {}, 0, 0.0
    from app.bt4_merge import list_mergeable_gaps
    for cid in ssm.list_runs():
        lf = ssm.load_factor(cid)
        fill[cid] = [round(float(x), 4) for x in lf]
        n_gaps += len(list_mergeable_gaps(ssm, cid))
        meta = ssm.get_segment_meta(cid)
        seg_km = (meta.km_cuoi - meta.km_dau).values
        cap = sum(ssm.get_state(cid, c).shape[0] for c in SEAT_CLASSES)
        cap_km += float(cap * seg_km.sum())
    reasons = {}
    for x in refusals:
        reasons[x["ly_do"]] = reasons.get(x["ly_do"], 0) + 1
    return {"policy": policy, "date": date, "sales": sales, "refusals": refusals,
            "refusal_reasons": reasons, "latency_ms": latency,
            "fill_matrix": fill, "n_gaps_cuoi": n_gaps, "cap_km_total": cap_km}

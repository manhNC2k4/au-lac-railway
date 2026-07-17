# -*- coding: utf-8 -*-
"""D2 — Bộ chỉ số chấm điểm theo đề bài (judging criteria).

Tính trên kết quả replay 1 policy: doanh thu, vé, pax-km & hệ số sử dụng pax-km,
fill-rate theo đoạn (ma trận heatmap), số gap ghép thành công, % khách phải đổi
chỗ, unmet demand, công bằng biến động giá, tốc độ tính lại (p95).
"""
import numpy as np


def summarize(result: dict) -> dict:
    """result: output của replay.run_policy (sales[], refusals[], seg_km, cap...)."""
    sales = result["sales"]
    n_sales = len(sales)
    rev = sum(s["gia"] for s in sales)
    paxkm = sum(s["d_km"] for s in sales)
    # pax-km utilization = pax-km bán / (sức chứa × km tuyến khả dụng)
    denom = result["cap_km_total"]
    util = paxkm / denom if denom else 0.0
    n_merge = sum(1 for s in sales if s["so_lan_doi_cho"] > 0)
    n_gapfill = sum(1 for s in sales if s.get("loai_ghe") == "gap_khit")
    ratios = [s["gia"] / max(s["f0"], 1) for s in sales]
    lat = result["latency_ms"]
    fill = result["fill_matrix"]          # {chuyen_id: [lf per seg]}
    lf_all = np.concatenate([np.asarray(v) for v in fill.values()]) if fill else np.array([0.0])
    return {
        "so_ve_ban": n_sales,
        "doanh_thu": int(rev),
        "pax_km": int(paxkm),
        "he_so_su_dung_pax_km": round(float(util), 4),
        "lf_binh_quan_doan": round(float(lf_all.mean()), 4),
        "so_doan_lf_cao": int((lf_all >= 0.85).sum()),
        "so_ghe_trong_cuc_bo": int(result.get("n_gaps_cuoi", 0)),
        "so_gap_ghep_thanh_cong": n_gapfill,
        "so_ve_ghep_nhieu_ghe": n_merge,
        "ty_le_khach_doi_cho": round(n_merge / max(n_sales, 1), 4),
        "so_yeu_cau_tu_choi": len(result["refusals"]),
        "ly_do_tu_choi": result["refusal_reasons"],
        "cong_bang_gia_std_ratio": round(float(np.std(ratios)), 4) if ratios else 0.0,
        "gia_tren_F0_bq": round(float(np.mean(ratios)), 4) if ratios else 0.0,
        "toc_do_tinh_lai_p95_ms": round(float(np.percentile(lat, 95)), 2) if lat else 0.0,
        "toc_do_tinh_lai_bq_ms": round(float(np.mean(lat)), 2) if lat else 0.0,
    }


def compare(fcfs: dict, ai: dict, z_opt: int | None = None) -> dict:
    """So sánh AI vs FCFS theo các target của đề bài."""
    def pct(a, b):
        return round((a - b) / max(b, 1e-9), 4)
    out = {
        "tang_doanh_thu": pct(ai["doanh_thu"], fcfs["doanh_thu"]),          # target +3..10%
        "tang_pax_km": pct(ai["pax_km"], fcfs["pax_km"]),                   # target +3..8%
        "tang_ve_ban": pct(ai["so_ve_ban"], fcfs["so_ve_ban"]),             # +10% dọc tuyến
        "giam_ghe_trong_cuc_bo": -pct(ai["so_ghe_trong_cuc_bo"],
                                      max(fcfs["so_ghe_trong_cuc_bo"], 1)),  # target -20%
        "giam_tu_choi_unmet": -pct(ai["so_yeu_cau_tu_choi"],
                                   max(fcfs["so_yeu_cau_tu_choi"], 1)),      # target -15%
        "ty_le_doi_cho_ai": ai["ty_le_khach_doi_cho"],                       # càng thấp càng tốt
    }
    if z_opt:
        out["hieu_suat_vs_toi_uu_offline"] = round(ai["doanh_thu"] / z_opt, 4)
        out["fcfs_vs_toi_uu_offline"] = round(fcfs["doanh_thu"] / z_opt, 4)
    return out

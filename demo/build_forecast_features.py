# -*- coding: utf-8 -*-
"""Trích xuất đặc trưng cho Bài toán con 1 (Demand Forecasting) — phương pháp PICKUP.

Grain output = "bảng hợp đồng": (train_id, origin, dest, seat_class, date)
  + nhãn q_final (tổng vé bán của chuyến đó — đích dự báo)
  + đặc trưng CHỈ DÙNG thông tin biết tại mốc u = U_FORECAST ngày trước khởi hành
    (leakage-safe theo thiết kế: vé có lead_time < u chưa tồn tại lúc dự báo).

Xuất: demo/features/forecast_features.parquet
      + demo/features/forecast_baseline_eval.txt (baseline pickup × mùa vụ, MASE)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parents[1] / "generated_data"
OUT = Path(__file__).resolve().parent / "features"
OUT.mkdir(exist_ok=True)

U_FORECAST = 14          # mốc dự báo: 14 ngày trước khởi hành
SPLIT_DATE = "2026-05-01"  # train < 01/5 (chế độ LUAT) | test >= 01/5 (chế độ AI)

# ---- macro seat class: gom tầng về 3 lớp cho grain gọn ----
MACRO = {"NGOI_MEM_DH": "NGOI", "NAM_K6_T1": "K6", "NAM_K6_T2": "K6", "NAM_K6_T3": "K6",
         "NAM_K4_T1": "K4", "NAM_K4_T2": "K4"}


def load():
    tx = pd.read_parquet(str(BASE / "data" / "transactions"),
                         columns=["mac_tau", "ngay_chay", "ga_di", "ga_den", "cu_ly_km",
                                  "loai_cho", "lead_time_ngay", "che_do_gia", "trang_thai"])
    tx = tx[tx.trang_thai == "HIEU_LUC"].copy()
    tx["ngay_chay"] = pd.to_datetime(tx["ngay_chay"])
    tx["seat_class"] = tx.loai_cho.map(MACRO)
    cal = pd.read_csv(BASE / "data" / "calendar_events.csv")
    cal = cal[pd.to_numeric(cal.tau_tet, errors="coerce").notna()].copy()
    cal["ngay"] = pd.to_datetime(cal["ngay"])
    for c in ("tau_tet", "dow", "H_horizon"):
        cal[c] = cal[c].astype(int)
    cal["la_le"] = cal["la_le"].astype(str).eq("True")
    return tx, cal


def build_features(tx: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    key = ["mac_tau", "ga_di", "ga_den", "seat_class", "ngay_chay"]
    # nhãn: tổng vé; đặc trưng pickup: vé đã bán tại u>=U_FORECAST (biết trước mốc dự báo)
    g = tx.groupby(key).agg(
        q_final=("lead_time_ngay", "size"),
        da_ban_truoc_u14=("lead_time_ngay", lambda s: int((s >= U_FORECAST).sum())),
        toc_do_ban_7d=("lead_time_ngay", lambda s: int(s.between(U_FORECAST, U_FORECAST + 7).sum())),
        cu_ly_km=("cu_ly_km", "first"),
    ).reset_index()
    # lịch âm tương đối (KHÔNG dùng month-of-year — Tết trượt 21 ngày giữa các năm)
    g = g.merge(cal[["ngay", "tau_tet", "dow", "la_le", "dot_ban_ve", "H_horizon",
                     "che_do_gia"]].rename(columns={"ngay": "ngay_chay"}), on="ngay_chay")
    g["sau_15_5"] = g.ngay_chay >= "2026-05-15"
    g["band"] = pd.cut(g.cu_ly_km, [0, 300, 900, 1800], labels=["ngan", "trung", "dai"])
    # trễ trên chuỗi (tàu, O, D, lớp chỗ): q_lag_7 & rolling 28 — shift để không rò rỉ
    g = g.sort_values("ngay_chay")
    grp = g.groupby(["mac_tau", "ga_di", "ga_den", "seat_class"], observed=True)["q_final"]
    g["q_lag_7"] = grp.shift(7)
    g["rolling_mean_28"] = grp.transform(lambda s: s.shift(1).rolling(28, min_periods=7).mean())
    return g


def baseline_pickup(g: pd.DataFrame) -> pd.DataFrame:
    """Baseline heuristic: q̂ = da_ban_truoc_u14 × ratio(band, tết?) — 'pickup' cổ điển.
    ratio ước lượng trên TRAIN, áp cho TEST. Đúng ghi chú demo: heuristic, giữ format."""
    tr = g[g.ngay_chay < SPLIT_DATE]
    te = g[g.ngay_chay >= SPLIT_DATE].copy()
    ratio = (tr.groupby(["band", tr.tau_tet.abs().le(21)], observed=True)
             .apply(lambda x: x.q_final.sum() / max(x.da_ban_truoc_u14.sum(), 1), include_groups=False)
             .rename("ratio").reset_index()
             .rename(columns={"tau_tet": "is_tet"}))
    te["is_tet"] = te.tau_tet.abs().le(21)
    te = te.merge(ratio, on=["band", "is_tet"], how="left")
    te["forecast_demand"] = (te.da_ban_truoc_u14 * te.ratio).round().clip(lower=0)
    return te


def evaluate(te: pd.DataFrame) -> str:
    err = (te.q_final - te.forecast_demand).abs()
    naive = (te.q_final - te.q_lag_7).abs()          # naive seasonal s=7 làm mẫu số MASE
    mase = err.mean() / max(naive.mean(), 1e-9)
    mu = te.forecast_demand.clip(lower=0.01)
    q = te.q_final
    poisson_dev = float(2 * (np.where(q > 0, q * np.log(q / mu), 0) - (q - mu)).mean())
    lines = [
        f"Mốc dự báo u={U_FORECAST} | split {SPLIT_DATE} (train=LUAT, test=AI)",
        f"Test rows: {len(te):,}",
        f"MASE (naive lag7): {mase:.3f}  (<1 = thắng naive)",
        f"Poisson deviance BQ: {poisson_dev:.3f}",
        f"Tổng dự báo/thực tế: {te.forecast_demand.sum():,.0f} / {te.q_final.sum():,.0f} "
        f"({te.forecast_demand.sum()/te.q_final.sum()-1:+.1%})",
    ]
    return "\n".join(lines)


def main():
    tx, cal = load()
    g = build_features(tx, cal)
    g.to_parquet(OUT / "forecast_features.parquet", index=False)
    te = baseline_pickup(g)
    # format "bảng hợp đồng" cho module sau
    contract = te.rename(columns={"ga_di": "origin", "ga_den": "dest", "mac_tau": "train_id",
                                  "ngay_chay": "date"})[
        ["origin", "dest", "date", "train_id", "seat_class", "forecast_demand"]]
    contract.to_csv(OUT / "forecast_output_contract.csv", index=False)
    rep = evaluate(te)
    (OUT / "forecast_baseline_eval.txt").write_text(rep, encoding="utf-8")
    print(f"Features: {len(g):,} dòng → {OUT/'forecast_features.parquet'}")
    print(f"Contract output (bài toán 1 → 3): {OUT/'forecast_output_contract.csv'}")
    print(rep)


if __name__ == "__main__":
    main()

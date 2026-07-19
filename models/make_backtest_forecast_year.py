# -*- coding: utf-8 -*-
"""Sinh forecast contract cho BACKTEST CẢ NĂM bằng rolling-cutoff theo THÁNG.

Mở rộng của make_backtest_forecast.py: thay vì 1 cutoff/lần chạy, load + build
features MỘT LẦN rồi với mỗi tháng M trong cửa sổ backtest, train model MỚI chỉ
trên ngay_chay < đầu tháng M và dự báo mọi ngày trong M (chỉ các tàu backtest).
Không leakage: model của tháng M chưa từng thấy dữ liệu từ M trở đi; đặc trưng
pickup (da_ban_truoc_u14...) là thông tin đã biết tại u=14.

Chạy: python models/make_backtest_forecast_year.py --start 2025-07 --end 2026-06
Xuất: artifacts/forecast_backtest_contract.csv (ghi đè, chỉ chứa các tàu backtest)
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ARTIFACTS
from models.train_bt1_forecast import (CAT_COLS, NUM_COLS, build_features, load,
                                       to_categorical)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-07")
    ap.add_argument("--end", default="2026-06")
    ap.add_argument("--trains", default="SE1,SE3,SE5,SE7")
    args = ap.parse_args()
    trains = args.trains.split(",")

    print("[BT1-year] load + build features (1 lần) ...", flush=True)
    tx, cal = load()
    g = build_features(tx, cal)
    del tx
    months = pd.period_range(args.start, args.end, freq="M")

    parts = []
    for m in months:
        t0 = time.time()
        start, end = m.to_timestamp(), (m + 1).to_timestamp()
        tr = g[g.ngay_chay < start]
        te = g[(g.ngay_chay >= start) & (g.ngay_chay < end)
               & (g.mac_tau.isin(trains))].copy()
        if not len(te):
            print(f"[BT1-year] {m}: không có dòng cần dự báo, bỏ qua", flush=True)
            continue
        Xtr, cats = to_categorical(tr[CAT_COLS + NUM_COLS], None)
        Xte, _ = to_categorical(te[CAT_COLS + NUM_COLS], cats)
        model = HistGradientBoostingRegressor(
            loss="poisson", learning_rate=0.06, max_iter=400, max_leaf_nodes=63,
            min_samples_leaf=40, l2_regularization=1.0, categorical_features="from_dtype",
            early_stopping=True, validation_fraction=0.1, random_state=20260717)
        model.fit(Xtr, tr.q_final.values)
        pred = np.clip(model.predict(Xte), 0, None)

        c = te[["ga_di", "ga_den", "ngay_chay", "mac_tau", "seat_class"]].copy()
        c.columns = ["origin", "dest", "date", "train_id", "seat_class"]
        c["forecast_demand"] = np.round(pred, 3)
        c["date"] = c["date"].dt.strftime("%Y-%m-%d")
        parts.append(c)
        mae = float(np.abs(te.q_final.values - pred).mean())
        print(f"[BT1-year] {m}: train {len(tr):,} | predict {len(te):,} | "
              f"MAE {mae:.2f} | n_iter {model.n_iter_} | {time.time()-t0:.0f}s", flush=True)

    out = ARTIFACTS / "forecast_backtest_contract.csv"
    contract = pd.concat(parts, ignore_index=True)
    contract.to_csv(out, index=False)
    print(f"[BT1-year] xuất -> {out} ({len(contract):,} dòng, {len(months)} tháng)", flush=True)


if __name__ == "__main__":
    main()

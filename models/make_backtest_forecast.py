# -*- coding: utf-8 -*-
"""Sinh forecast contract cho các ngày BACKTEST nằm ngoài vùng phủ của model chính.

Vấn đề: model chính train < 01/5/2026, contract chỉ phủ ≥ 01/5. Ngày backtest Tết
(02/2026) không có forecast => bid price = 0 => BT3/BT5 mù khan hiếm dịp Tết.

Cách làm TRUNG THỰC (không leakage): với mỗi cutoff, train model MỚI chỉ trên
ngay_chay < cutoff, rồi dự báo các ngày mục tiêu sau cutoff. Đặc trưng pickup
(da_ban_truoc_u14...) là thông tin biết tại u=14 — hợp lệ tại thời điểm dự báo.

Chạy: python models/make_backtest_forecast.py --cutoff 2026-02-01 --dates 2026-02-14
Xuất: artifacts/forecast_backtest_contract.csv (append theo ngày, dedupe)
"""
import argparse
import sys
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
    ap.add_argument("--cutoff", default="2026-02-01")
    ap.add_argument("--dates", default="2026-02-14")
    args = ap.parse_args()
    dates = args.dates.split(",")

    print(f"[BT1-bt] load + build features (cutoff {args.cutoff}, dates {dates}) ...")
    tx, cal = load()
    g = build_features(tx, cal)
    tr = g[g.ngay_chay < args.cutoff].copy()
    te = g[g.ngay_chay.isin(pd.to_datetime(dates))].copy()
    print(f"[BT1-bt] train {len(tr):,} dòng | predict {len(te):,} dòng")

    Xtr, cats = to_categorical(tr[CAT_COLS + NUM_COLS], None)
    Xte, _ = to_categorical(te[CAT_COLS + NUM_COLS], cats)
    model = HistGradientBoostingRegressor(
        loss="poisson", learning_rate=0.06, max_iter=400, max_leaf_nodes=63,
        min_samples_leaf=40, l2_regularization=1.0, categorical_features="from_dtype",
        early_stopping=True, validation_fraction=0.1, random_state=20260717)
    model.fit(Xtr, tr.q_final.values)
    pred = np.clip(model.predict(Xte), 0, None)

    contract = te[["ga_di", "ga_den", "ngay_chay", "mac_tau", "seat_class"]].copy()
    contract.columns = ["origin", "dest", "date", "train_id", "seat_class"]
    contract["forecast_demand"] = np.round(pred, 3)
    contract["date"] = contract["date"].dt.strftime("%Y-%m-%d")

    out = ARTIFACTS / "forecast_backtest_contract.csv"
    if out.exists():
        old = pd.read_csv(out)
        old = old[~old.date.isin(dates)]
        contract = pd.concat([old, contract], ignore_index=True)
    contract.to_csv(out, index=False)
    err = np.abs(te.q_final.values - pred).mean()
    print(f"[BT1-bt] MAE trên ngày backtest: {err:.2f} vé/grain | tổng dự báo/thực: "
          f"{pred.sum():,.0f}/{te.q_final.sum():,.0f}")
    print(f"[BT1-bt] xuất -> {out} ({len(contract):,} dòng)")


if __name__ == "__main__":
    main()

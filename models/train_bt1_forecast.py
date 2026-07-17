# -*- coding: utf-8 -*-
"""BÀI TOÁN CON 1 — Demand Forecasting: TRAIN + xuất model cho FastAPI.

Model thật: HistGradientBoostingRegressor(loss="poisson") — cầu là dữ liệu ĐẾM thưa
(doc 02 §10.1 => MASE/Poisson deviance, không MAPE). Đặc trưng leakage-safe tại
u=14 ngày trước khởi hành. Split theo ngay_chay tại điểm gãy chế độ 01/5/2026
(train=LUAT, test=AI) — đúng bất biến "split by ngay_chay", không split theo lúc mua.

Xuất:
  artifacts/bt1_forecast_hgb.joblib     — model đã fit
  artifacts/bt1_feature_spec.json       — cột số / cột hạng mục + vocab để serve
  ../demo hoặc artifacts/forecast_output_contract.csv — bảng dự báo đúng format hợp đồng
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_poisson_deviance

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import (ARTIFACTS, BAND_EDGES, BAND_LABELS, DATA, REGIME_BREAK,
                        U_FORECAST)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MACRO = {"NGOI_MEM_DH": "NGOI", "NAM_K6_T1": "K6", "NAM_K6_T2": "K6", "NAM_K6_T3": "K6",
         "NAM_K4_T1": "K4", "NAM_K4_T2": "K4"}
KEY = ["mac_tau", "ga_di", "ga_den", "seat_class", "ngay_chay"]
CAT_COLS = ["mac_tau", "ga_di", "ga_den", "seat_class", "band", "dot_ban_ve", "che_do_gia", "dow"]
NUM_COLS = ["da_ban_truoc_u14", "toc_do_ban_7d", "cu_ly_km", "tau_tet", "la_le",
            "H_horizon", "sau_15_5", "q_lag_7", "rolling_mean_28"]


def load():
    tx = pd.read_parquet(str(DATA / "transactions"),
                         columns=["mac_tau", "ngay_chay", "ga_di", "ga_den", "cu_ly_km",
                                  "loai_cho", "lead_time_ngay", "trang_thai"])
    tx = tx[tx.trang_thai == "HIEU_LUC"].copy()
    tx["ngay_chay"] = pd.to_datetime(tx["ngay_chay"])
    tx["seat_class"] = tx.loai_cho.map(MACRO)
    cal = pd.read_csv(DATA / "calendar_events.csv")
    cal = cal[pd.to_numeric(cal.tau_tet, errors="coerce").notna()].copy()
    cal["ngay"] = pd.to_datetime(cal["ngay"])
    for c in ("tau_tet", "dow", "H_horizon"):
        cal[c] = cal[c].astype(int)
    cal["la_le"] = cal["la_le"].astype(str).eq("True").astype(int)
    return tx, cal


def build_features(tx, cal):
    # vectorized (không lambda per-group) — nhanh trên vài triệu nhóm
    tx = tx.assign(_u14=(tx.lead_time_ngay >= U_FORECAST),
                   _7d=tx.lead_time_ngay.between(U_FORECAST, U_FORECAST + 7))
    g = tx.groupby(KEY, observed=True).agg(
        q_final=("lead_time_ngay", "size"),
        da_ban_truoc_u14=("_u14", "sum"),
        toc_do_ban_7d=("_7d", "sum"),
        cu_ly_km=("cu_ly_km", "first"),
    ).reset_index()
    g["da_ban_truoc_u14"] = g["da_ban_truoc_u14"].astype(int)
    g["toc_do_ban_7d"] = g["toc_do_ban_7d"].astype(int)
    g = g.merge(cal[["ngay", "tau_tet", "dow", "la_le", "dot_ban_ve", "H_horizon", "che_do_gia"]]
                .rename(columns={"ngay": "ngay_chay", "H_horizon": "H_horizon"}), on="ngay_chay")
    g = g.rename(columns={"H_horizon": "H_horizon"})
    g["H_horizon"] = g["H_horizon"].astype(int)
    g["sau_15_5"] = (g.ngay_chay >= "2026-05-15").astype(int)
    g["band"] = pd.cut(g.cu_ly_km, BAND_EDGES, labels=BAND_LABELS).astype(object)
    g = g.sort_values("ngay_chay")
    grp = g.groupby(["mac_tau", "ga_di", "ga_den", "seat_class"], observed=True)["q_final"]
    g["q_lag_7"] = grp.shift(7)
    g["rolling_mean_28"] = grp.transform(lambda s: s.shift(1).rolling(28, min_periods=7).mean())
    g["dow"] = g["dow"].astype(str)
    return g


def to_categorical(df, categories: dict | None):
    """Đưa cột hạng mục về dtype category. Nếu có `categories` (khi serve) thì khóa vocab."""
    df = df.copy()
    cats_out = {}
    for c in CAT_COLS:
        if categories is None:
            df[c] = df[c].astype("category")
            cats_out[c] = df[c].cat.categories.tolist()
        else:
            df[c] = pd.Categorical(df[c], categories=categories[c])
    return df, cats_out


def baseline_pickup(g):
    """Heuristic pickup × mùa vụ (để so sánh với model)."""
    tr = g[g.ngay_chay < REGIME_BREAK]
    te = g[g.ngay_chay >= REGIME_BREAK].copy()
    ratio = (tr.assign(is_tet=tr.tau_tet.abs().le(21))
             .groupby(["band", "is_tet"], observed=True)
             .apply(lambda x: x.q_final.sum() / max(x.da_ban_truoc_u14.sum(), 1), include_groups=False)
             .rename("ratio").reset_index())
    te["is_tet"] = te.tau_tet.abs().le(21)
    te = te.merge(ratio, on=["band", "is_tet"], how="left")
    te["yhat"] = (te.da_ban_truoc_u14 * te.ratio.fillna(1.0)).clip(lower=0)
    return te


def mase(y, yhat, y_naive):
    err = np.abs(y - yhat).mean()
    naive = np.abs(y - y_naive).mean()
    return err / max(naive, 1e-9)


def main():
    print("[BT1] load + build features ...")
    tx, cal = load()
    g = build_features(tx, cal)
    tr = g[g.ngay_chay < REGIME_BREAK].copy()
    te = g[g.ngay_chay >= REGIME_BREAK].copy()
    print(f"[BT1] grain rows: {len(g):,} | train(LUAT) {len(tr):,} | test(AI) {len(te):,}")

    Xtr, cats = to_categorical(tr[CAT_COLS + NUM_COLS], None)
    Xte, _ = to_categorical(te[CAT_COLS + NUM_COLS], cats)
    ytr, yte = tr.q_final.values, te.q_final.values

    model = HistGradientBoostingRegressor(
        loss="poisson", learning_rate=0.06, max_iter=600, max_leaf_nodes=63,
        min_samples_leaf=40, l2_regularization=1.0, categorical_features="from_dtype",
        early_stopping=True, validation_fraction=0.1, random_state=20260717)
    print("[BT1] fit HistGradientBoostingRegressor(loss=poisson) ...")
    model.fit(Xtr, ytr)

    pred = np.clip(model.predict(Xte), 0, None)
    y_naive = te.q_lag_7.fillna(te.rolling_mean_28).fillna(te.da_ban_truoc_u14).values
    base = baseline_pickup(g)
    rep = {
        "test_rows": int(len(te)),
        "MASE_model": round(float(mase(yte, pred, y_naive)), 4),
        "MASE_baseline_pickup": round(float(mase(base.q_final, base.yhat,
                                    base.q_lag_7.fillna(base.da_ban_truoc_u14))), 4),
        "poisson_deviance_model": round(float(mean_poisson_deviance(
            np.clip(yte, 1e-9, None), np.clip(pred, 1e-9, None))), 4),
        "bias_model_pct": round(float(pred.sum() / yte.sum() - 1), 4),
        "n_iter": int(model.n_iter_),
    }

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ARTIFACTS / "bt1_forecast_hgb.joblib")
    spec = {"cat_cols": CAT_COLS, "num_cols": NUM_COLS, "cat_categories": cats,
            "u_forecast": U_FORECAST, "regime_break": REGIME_BREAK, "label": "q_final",
            "metrics": rep}
    (ARTIFACTS / "bt1_feature_spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    # bảng hợp đồng cho BT3 (đúng format {origin,dest,date,train_id,seat_class,forecast_demand})
    contract = te[["ga_di", "ga_den", "ngay_chay", "mac_tau", "seat_class"]].copy()
    contract.columns = ["origin", "dest", "date", "train_id", "seat_class"]
    contract["forecast_demand"] = np.round(pred, 3)
    contract["date"] = contract["date"].dt.strftime("%Y-%m-%d")
    contract.to_csv(ARTIFACTS / "forecast_output_contract.csv", index=False)

    print("[BT1] metrics:", json.dumps(rep, ensure_ascii=False))
    print(f"[BT1] xuất -> {ARTIFACTS/'bt1_forecast_hgb.joblib'}")
    print(f"[BT1] contract -> {ARTIFACTS/'forecast_output_contract.csv'} ({len(contract):,} dòng)")


if __name__ == "__main__":
    main()

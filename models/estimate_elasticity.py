# -*- coding: utf-8 -*-
"""Ước lượng ĐỘ CO GIÃN GIÁ (đường cầu) từ search_log — CHỈ dữ liệu quan sát được.

Ý tưởng: quyết định mua trong generator là wtp < p_ny, mà cả wtp lẫn p_ny đều tỉ lệ
với F0 theo tier => xác suất mua chỉ phụ thuộc r = gia_niem_yet/gia_goc (tier triệt
tiêu). Ta ước lượng P(mua | r, ngữ cảnh KHÔNG cá nhân) bằng logistic:

    logit P(mua) = β0 + β_r·ln(r) + β_band·band + β_tet·tet + β_lead·lead_bin

- Tử số (mua) & giá r: từ transactions (mỗi vé = 1 lần mua, r = niêm_yết/gốc).
- Mẫu số (không mua vì giá): từ search_log ket_qua=BO_VI_GIA.
- Ghép theo cell (chuyen_id, ga_di, ga_den, lead_bin) => giá r gần như cố định trong
  cell (giá tất định theo trạng thái) => gán r cho nhóm BO_VI_GIA cùng cell.
- KHÔNG dùng phan_khuc (mục đích chuyến = dữ liệu cá nhân) => giá công bằng, không
  phân biệt đối xử. Loại TU_CHOI_HET_CHO (từ chối do hết chỗ, không phải quyết định giá).

Loại các ngày backtest khỏi tập ước lượng => không rò rỉ.
Xuất: artifacts/elasticity_params.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ARTIFACTS, BAND_EDGES, BAND_LABELS, DATA

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEAD_EDGES = [-1, 3, 7, 14, 30, 999]
LEAD_LABELS = ["0-3", "4-7", "8-14", "15-30", "30+"]
R_EDGES = np.round(np.arange(0.5, 1.65, 0.1), 2)     # bin giá r


def lead_bin(u):
    return pd.cut(u, LEAD_EDGES, labels=LEAD_LABELS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exclude-dates", default="2026-02-14,2026-05-20")
    args = ap.parse_args()
    excl = set(args.exclude_dates.split(","))

    # tết: ngày có |tau_tet| <= 21
    cal = pd.read_csv(DATA / "calendar_events.csv")
    cal = cal[pd.to_numeric(cal.tau_tet, errors="coerce").notna()]
    tet_days = set(cal[cal.tau_tet.astype(int).abs() <= 21].ngay)

    print("[ELAST] đọc transactions (mẫu MUA + giá r) ...")
    tx = pd.read_parquet(str(DATA / "transactions"),
                         columns=["chuyen_id", "ngay_chay", "ga_di", "ga_den", "cu_ly_km",
                                  "lead_time_ngay", "gia_goc", "gia_niem_yet", "trang_thai"])
    tx = tx[(tx.trang_thai == "HIEU_LUC") & (~tx.ngay_chay.isin(excl))].copy()
    tx["r"] = tx.gia_niem_yet / tx.gia_goc
    tx["lb"] = lead_bin(tx.lead_time_ngay).astype(str)
    mua = (tx.groupby(["chuyen_id", "ga_di", "ga_den", "lb"], observed=True)
           .agg(n_mua=("r", "size"), r=("r", "mean"), cu_ly_km=("cu_ly_km", "first"),
                ngay=("ngay_chay", "first")).reset_index())

    print("[ELAST] đọc search_log (mẫu BO_VI_GIA) ...")
    sl = pd.read_parquet(str(DATA / "search_log"),
                         columns=["ngay_di", "lead_time_ngay", "ga_di", "ga_den",
                                  "chuyen_id", "ket_qua"])
    bo = sl[(sl.ket_qua == "BO_VI_GIA") & (~sl.ngay_di.isin(excl))].copy()
    bo["lb"] = lead_bin(bo.lead_time_ngay).astype(str)
    nbo = (bo.groupby(["chuyen_id", "ga_di", "ga_den", "lb"], observed=True)
           .size().rename("n_bo").reset_index())

    # ghép cell: tử số (mua, có r) + mẫu số (bỏ vì giá)
    cell = mua.merge(nbo, on=["chuyen_id", "ga_di", "ga_den", "lb"], how="left")
    cell["n_bo"] = cell.n_bo.fillna(0).astype(int)
    cell["is_tet"] = cell.ngay.isin(tet_days).astype(int)
    cell["band"] = pd.cut(cell.cu_ly_km, BAND_EDGES, labels=BAND_LABELS).astype(str)
    cell["r_bin"] = pd.cut(cell.r, R_EDGES).astype(str)
    print(f"[ELAST] {len(cell):,} cell | tổng mua {cell.n_mua.sum():,} | bỏ giá {cell.n_bo.sum():,}")

    # gộp về (band, tet, lead, r_bin) => tần suất mua theo r
    agg = (cell.groupby(["band", "is_tet", "lb", "r_bin"], observed=True)
           .agg(n_mua=("n_mua", "sum"), n_bo=("n_bo", "sum"), r=("r", "mean")).reset_index())
    agg = agg[agg.r.notna() & ((agg.n_mua + agg.n_bo) >= 20)]

    # dựng dataset logistic: mỗi cell -> 1 dòng mua (w=n_mua) + 1 dòng bỏ (w=n_bo)
    rows, y, w = [], [], []
    for t in agg.itertuples(index=False):
        feat = _features(t.r, t.band, t.is_tet, t.lb)
        rows.append(feat); y.append(1); w.append(t.n_mua)
        rows.append(feat); y.append(0); w.append(t.n_bo)
    X = np.array(rows); y = np.array(y); w = np.array(w, float)
    clf = LogisticRegression(max_iter=1000, C=10.0)
    clf.fit(X, y, sample_weight=w)

    names = _feat_names()
    params = {"intercept": float(clf.intercept_[0]),
              "coef": {n: float(c) for n, c in zip(names, clf.coef_[0])},
              "beta_ln_r": float(clf.coef_[0][0]),
              "bands": BAND_LABELS, "lead_labels": LEAD_LABELS, "lead_edges": LEAD_EDGES,
              "band_edges": BAND_EDGES, "_source": "search_log MUA/BO_VI_GIA, loại ngày backtest"}
    # kiểm tra: co giãn tại r=1
    p1 = _sigmoid(clf.intercept_[0] + clf.coef_[0] @ _features(1.0, "trung", 0, "8-14"))
    p12 = _sigmoid(clf.intercept_[0] + clf.coef_[0] @ _features(1.2, "trung", 0, "8-14"))
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "elasticity_params.json").write_text(
        json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ELAST] β_ln(r) = {params['beta_ln_r']:.3f} (âm = cầu giảm khi giá tăng)")
    print(f"[ELAST] P(mua|r=1.0, trung, thường, u8-14) = {p1:.3f} | r=1.2 => {p12:.3f}")
    print(f"[ELAST] xuất -> {ARTIFACTS / 'elasticity_params.json'}")


def _features(r, band, tet, lb):
    f = [np.log(max(r, 1e-3))]
    f += [1.0 if band == b else 0.0 for b in BAND_LABELS[1:]]     # dai, (trung ref)
    f += [float(tet)]
    f += [1.0 if lb == x else 0.0 for x in LEAD_LABELS[1:]]
    return np.array(f)


def _feat_names():
    return (["ln_r"] + [f"band_{b}" for b in BAND_LABELS[1:]] + ["is_tet"]
            + [f"lead_{x}" for x in LEAD_LABELS[1:]])


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Train LightGBM Poisson cho Bài toán con 1 (Demand Forecasting), grain như
build_forecast_features.py: (mac_tau, ga_di, ga_den, seat_class, ngay_chay).

Sửa leakage so với parquet gốc: q_lag_7 / rolling_mean_28 dùng thông tin của các
chuyến CHƯA khởi hành tại mốc u=14 (và shift theo dòng, không theo ngày lịch).
Ở đây loại bỏ chúng, dựng lại lag an toàn theo NGÀY LỊCH với lag >= 15 ngày
(chuyến tham chiếu đã khởi hành trước mốc dự báo): q_lag_15/21/28/35 + trung
bình các lag có mặt.

Split (doc 03 §9.1 — theo ngay_chay, không bao giờ theo thời điểm mua):
  train-core < 2026-03-01 | embargo 14 ngày | valid 2026-03-15..2026-04-30
  test >= 2026-05-01 (chế độ AI) — chỉ chấm ở bước --final, không dùng để tune.

Learning rate LINH HOẠT trong lúc train (chọn 1 hoặc kết hợp):
  --lr-decay 0.999   : decay mũ theo vòng lặp  lr_t = lr0 * decay^t
  --lr-adapt         : ReduceLROnPlateau — valid poisson không cải thiện
                       `--lr-patience` vòng thì nhân lr với `--lr-factor`,
                       không xuống dưới `--lr-min`; mỗi lần đổi có log [LR].

Dùng:
  python demo/train_forecast.py --tag t1 --lr 0.08 --lr-adapt          # 1 trial tune
  python demo/train_forecast.py --final --tag final --lr-adapt         # refit + chấm test
Log JSONL: demo/train_out/tuning_log.jsonl (mỗi trial 1 dòng, đọc để tinh chỉnh).
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
FEAT = HERE / "features" / "forecast_features.parquet"
OUT = HERE / "train_out"
OUT.mkdir(exist_ok=True)
LOG = OUT / "tuning_log.jsonl"

KEY = ["mac_tau", "ga_di", "ga_den", "seat_class"]
SPLIT_TEST = "2026-05-01"      # điểm gãy chế độ LUAT -> AI
VALID_LO, VALID_HI = "2026-03-15", "2026-05-01"
TRAIN_CORE_HI = "2026-03-01"   # embargo 14 ngày trước valid
SAFE_LAGS = [15, 21, 28, 35]   # lag ngày lịch, chuyến tham chiếu đã chạy trước u=14

CAT_COLS = ["mac_tau", "ga_di", "ga_den", "seat_class", "band", "dot_ban_ve", "che_do_gia"]
NUM_COLS = ["da_ban_truoc_u14", "toc_do_ban_7d", "cu_ly_km", "tau_tet", "dow",
            "la_le", "H_horizon", "sau_15_5"]


def build_safe_lags(g: pd.DataFrame) -> pd.DataFrame:
    """Lag theo ngày lịch bằng self-merge (chuỗi thưa: ngày thiếu -> NaN, LGBM tự xử)."""
    base = g[KEY + ["ngay_chay", "q_final"]]
    for L in SAFE_LAGS:
        ref = base.rename(columns={"q_final": f"q_lag_{L}"}).copy()
        ref["ngay_chay"] = ref["ngay_chay"] + pd.Timedelta(days=L)
        g = g.merge(ref, on=KEY + ["ngay_chay"], how="left")
    lag_cols = [f"q_lag_{L}" for L in SAFE_LAGS]
    g["lag_mean"] = g[lag_cols].mean(axis=1)
    return g


def load() -> pd.DataFrame:
    g = pd.read_parquet(FEAT)
    g = g.drop(columns=["q_lag_7", "rolling_mean_28"])   # leakage tại u=14
    g = build_safe_lags(g)
    for c in CAT_COLS:
        g[c] = g[c].astype("category")
    for c in ("la_le", "sau_15_5"):
        g[c] = g[c].astype(int)
    return g


def feature_cols(g):
    return NUM_COLS + CAT_COLS + [c for c in g.columns if c.startswith("q_lag_")] + ["lag_mean"]


class AdaptiveLR:
    """Callback ReduceLROnPlateau cho LightGBM: valid poisson không cải thiện
    `patience` vòng => lr *= factor (sàn lr_min). Ghi lại lịch sử đổi lr."""

    order = 5  # chạy trước early_stopping (order=30)

    def __init__(self, lr0, factor=0.5, patience=60, lr_min=1e-3, decay=1.0):
        self.lr = lr0
        self.factor, self.patience, self.lr_min, self.decay = factor, patience, lr_min, decay
        self.best = float("inf")
        self.wait = 0
        self.history = []

    def __call__(self, env):
        new_lr = self.lr
        if self.decay < 1.0:                      # decay mũ theo vòng
            new_lr = max(self.lr * self.decay, self.lr_min)
        # env.evaluation_result_list: [(name, metric, value, is_higher_better), ...]
        val = next((v for n, m, v, _ in env.evaluation_result_list if n == "valid"), None)
        if val is not None:
            if val < self.best - 1e-9:
                self.best, self.wait = val, 0
            else:
                self.wait += 1
                if self.wait >= self.patience and self.lr > self.lr_min:
                    new_lr = max(self.lr * self.factor, self.lr_min)
                    self.wait = 0
                    self.history.append({"iter": env.iteration, "lr": round(new_lr, 6),
                                         "valid_poisson": round(val, 6)})
                    print(f"[LR] iter {env.iteration}: plateau {self.patience} vòng "
                          f"=> lr {self.lr:.4g} -> {new_lr:.4g}", flush=True)
        if new_lr != self.lr:
            self.lr = new_lr
            env.model.reset_parameter({"learning_rate": self.lr})


def metrics(y, mu, naive_ref):
    """MASE (mẫu số |y - q_lag_15| — naive an toàn cùng grain) + Poisson deviance + bias."""
    err = np.abs(y - mu)
    na = np.abs(y - naive_ref)
    na_mean = np.nanmean(na)
    mu_c = np.clip(mu, 0.01, None)
    dev = float(2 * np.mean(np.where(y > 0, y * np.log(y / mu_c), 0) - (y - mu_c)))
    return {"mase": float(err.mean() / max(na_mean, 1e-9)),
            "poisson_dev": dev,
            "bias_pct": float(mu.sum() / y.sum() - 1),
            "mae": float(err.mean())}


def run_trial(g, params, rounds, tag, lr_cfg, final=False):
    fc = feature_cols(g)
    d = g.ngay_chay
    tr_core = g[d < TRAIN_CORE_HI]
    va = g[(d >= VALID_LO) & (d < VALID_HI)]
    te = g[d >= SPLIT_TEST]

    t0 = time.time()
    dtr = lgb.Dataset(tr_core[fc], tr_core.q_final, categorical_feature=CAT_COLS)
    dva = lgb.Dataset(va[fc], va.q_final, reference=dtr)
    evals = {}
    lr_cb = AdaptiveLR(params["learning_rate"], factor=lr_cfg["factor"],
                       patience=lr_cfg["patience"], lr_min=lr_cfg["lr_min"],
                       decay=lr_cfg["decay"]) if lr_cfg["on"] else None
    cbs = [lgb.early_stopping(150, verbose=False), lgb.record_evaluation(evals),
           lgb.log_evaluation(period=100)]
    if lr_cb:
        cbs.insert(0, lr_cb)
    model = lgb.train(params, dtr, num_boost_round=rounds, valid_sets=[dtr, dva],
                      valid_names=["train", "valid"], callbacks=cbs)
    best_iter = model.best_iteration
    mu_va = model.predict(va[fc], num_iteration=best_iter)
    m_va = metrics(va.q_final.values, mu_va, va.q_lag_15.values)

    rec = {"tag": tag, "params": {k: v for k, v in params.items() if k != "verbosity"},
           "rounds": rounds, "best_iter": best_iter,
           "lr_schedule": lr_cb.history if lr_cb else None,
           "lr_final": lr_cb.lr if lr_cb else params["learning_rate"],
           "valid": m_va, "n_train": len(tr_core), "n_valid": len(va),
           "sec": round(time.time() - t0, 1)}

    if final:
        # refit trên toàn bộ giai đoạn LUAT (< 01/5) với best_iter đã chọn
        full = g[d < SPLIT_TEST]
        dfull = lgb.Dataset(full[fc], full.q_final, categorical_feature=CAT_COLS)
        n_final = max(int(best_iter * len(full) / max(len(tr_core), 1)), best_iter)
        # replay lịch lr đã học ở pha tune (không có valid khi refit => không adapt được)
        final_cbs = []
        if lr_cb and lr_cb.history:
            sched, cur = [], params["learning_rate"]
            changes = {h["iter"]: h["lr"] for h in lr_cb.history}
            for i in range(n_final):
                cur = changes.get(i, cur)
                sched.append(cur)
            final_cbs.append(lgb.reset_parameter(learning_rate=sched))
        model = lgb.train(params, dfull, num_boost_round=n_final, callbacks=final_cbs)
        mu_te = model.predict(te[fc])
        m_te = metrics(te.q_final.values, mu_te, te.q_lag_15.values)
        # so sánh trực tiếp với naive lag7 (mẫu số của baseline pickup cũ) để đối chiếu
        old = pd.read_parquet(FEAT, columns=KEY + ["ngay_chay", "q_lag_7"])
        te_old = te.merge(old, on=KEY + ["ngay_chay"], how="left")
        na7 = np.abs(te.q_final.values - te_old.q_lag_7.values)
        m_te["mase_vs_lag7"] = float(np.abs(te.q_final.values - mu_te).mean()
                                     / max(np.nanmean(na7), 1e-9))
        rec["test"] = m_te
        rec["n_final_rounds"] = n_final
        with (OUT / "model_final.pkl").open("wb") as f:
            pickle.dump(model, f)             # load: pickle.load(f) -> lgb.Booster
        model.save_model(str(OUT / "model_final.txt"))  # bản text để soi cây/debug
        pred = te[KEY + ["ngay_chay", "q_final"]].copy()
        pred["forecast_demand"] = mu_te
        pred.to_parquet(OUT / "test_predictions.parquet", index=False)
        imp = pd.Series(model.feature_importance("gain"), index=fc).sort_values(ascending=False)
        (OUT / "feature_importance.txt").write_text(imp.round(0).to_string(), encoding="utf-8")
        # breakdown theo băng cự ly x cửa sổ Tết (chẩn đoán bias cấu trúc)
        bd = pred.assign(band=te["band"].values,
                         is_tet=te.tau_tet.abs().le(21).values).groupby(
            ["band", "is_tet"], observed=True).apply(
            lambda x: pd.Series({"n": len(x),
                                 "bias_pct": x.forecast_demand.sum() / x.q_final.sum() - 1,
                                 "mae": (x.q_final - x.forecast_demand).abs().mean()}),
            include_groups=False)
        rec["test_breakdown"] = json.loads(bd.round(4).reset_index().to_json(orient="records"))

    OUT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(rec, ensure_ascii=False, indent=2, default=str))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="trial")
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument("--leaves", type=int, default=127)
    ap.add_argument("--min-data", type=int, default=200)
    ap.add_argument("--ff", type=float, default=0.9, help="feature_fraction")
    ap.add_argument("--bf", type=float, default=0.9, help="bagging_fraction")
    ap.add_argument("--l2", type=float, default=0.0)
    ap.add_argument("--rounds", type=int, default=3000)
    ap.add_argument("--final", action="store_true", help="refit toàn LUAT + chấm test AI")
    # --- learning rate linh hoạt ---
    ap.add_argument("--lr-adapt", action="store_true",
                    help="giảm lr khi valid poisson plateau (ReduceLROnPlateau)")
    ap.add_argument("--lr-patience", type=int, default=60)
    ap.add_argument("--lr-factor", type=float, default=0.5)
    ap.add_argument("--lr-min", type=float, default=1e-3)
    ap.add_argument("--lr-decay", type=float, default=1.0,
                    help="<1.0 = decay mũ theo vòng, vd 0.999")
    args = ap.parse_args()

    params = {"objective": "poisson", "metric": "poisson",
              "learning_rate": args.lr, "num_leaves": args.leaves,
              "min_data_in_leaf": args.min_data,
              "feature_fraction": args.ff, "bagging_fraction": args.bf,
              "bagging_freq": 1, "lambda_l2": args.l2,
              "num_threads": 0, "verbosity": -1, "seed": 20260717}

    lr_cfg = {"on": args.lr_adapt or args.lr_decay < 1.0,
              "patience": args.lr_patience, "factor": args.lr_factor,
              "lr_min": args.lr_min, "decay": args.lr_decay}

    print(f"[{args.tag}] load + build safe lags ...", flush=True)
    g = load()
    print(f"rows={len(g):,} | features={len(feature_cols(g))} | lr_cfg={lr_cfg}", flush=True)
    run_trial(g, params, args.rounds, args.tag, lr_cfg, final=args.final)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Backtest CẢ NĂM (AI vs FCFS) — phiên bản tối ưu cho hàng trăm ngày.

Khác eval/backtest.py (vài ngày): load_day gốc đọc lại wtp.parquet 35M dòng cho
TỪNG ngày. Ở đây:
  1. Phase CACHE: đọc wtp MỘT LẦN, join sẵn requests (search_log + wtp + tier)
     cho từng tháng -> parquet nhỏ.
  2. Phase RUN: chạy song song N worker theo ngày (mỗi ngày độc lập — SSM dựng
     riêng), ghi kết quả tăng dần vào JSONL (chạy lại sẽ bỏ qua ngày đã xong).
  3. Phase REPORT: tổng hợp -> models/artifacts/backtest_year_report.json
     + bảng minh chứng theo ngày models/artifacts/backtest_year_daily.csv.

Chạy: python eval/backtest_year.py --start 2025-07-01 --end 2026-06-30 \
        --trains SE1,SE3,SE5,SE7 --workers 4 --cache-dir <dir>
"""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ARTIFACTS, DATA, load_calendar, mac_tau_of
from eval.metrics import compare, summarize

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GT = DATA.parent / "_ground_truth"


# ---------------------------------------------------------------- cache phase
def build_cache(months: list[str], trains: list[str], cache_dir: Path):
    from eval.replay import SEAT_CLASSES, TIERS, _frac
    cache_dir.mkdir(parents=True, exist_ok=True)
    todo = [m for m in months if not (cache_dir / f"req_{m}.parquet").exists()]
    if not todo:
        print("[CACHE] đủ cache, bỏ qua", flush=True)
        return
    print(f"[CACHE] đọc wtp.parquet (1 lần) cho {len(todo)} tháng ...", flush=True)
    wtp = pd.read_parquet(GT / "wtp.parquet")
    for m in todo:
        sl = pd.read_parquet(str(DATA / "search_log" / f"thang={m}"))
        sl = sl[sl.chuyen_id.notna()]      # lượt tìm không khớp chuyến -> bỏ
        sl["mac"] = sl.chuyen_id.map(mac_tau_of)
        sl = sl[sl.mac.isin(trains)].copy()
        tx = pd.read_parquet(str(DATA / "transactions" / f"thang={m}"),
                             columns=["yeu_cau_id", "loai_cho"])
        sl = sl.merge(wtp, on="yeu_cau_id", how="left")
        tier_map = dict(zip(tx.yeu_cau_id, tx.loai_cho))
        sl["tier"] = sl.yeu_cau_id.map(tier_map)

        def pick_tier(rq):
            cls = SEAT_CLASSES[int(_frac(rq, "cls") * 3)]
            ts = TIERS[cls]
            return ts[int(_frac(rq, "tier") * len(ts))]
        na = sl.tier.isna()
        sl.loc[na, "tier"] = [pick_tier(r) for r in sl.loc[na, "yeu_cau_id"]]
        sl = sl.sort_values("lead_time_ngay", ascending=False)
        sl.to_parquet(cache_dir / f"req_{m}.parquet", index=False)
        print(f"[CACHE] {m}: {len(sl):,} yêu cầu", flush=True)


# ---------------------------------------------------------------- run phase
_Z_OPT = None


def _z_opt_for(date: str, trains: list[str]) -> int:
    global _Z_OPT
    if _Z_OPT is None:
        _Z_OPT = pd.read_parquet(GT / "offline_optimum.parquet")
    runs = [f"RUN:{t}:{date}" for t in trains]
    sel = _Z_OPT[_Z_OPT.chuyen_id.isin(runs)]
    return int(sel.z_opt.sum()) if len(sel) else 0


def run_one_date(args_tuple):
    date, trains, cache_dir = args_tuple
    from eval.replay import run_policy          # import trong worker
    df = pd.read_parquet(Path(cache_dir) / f"req_{date[:7]}.parquet")
    df = df[df.ngay_di == date]
    if not len(df):
        return {"date": date, "empty": True}
    res = {}
    for pol in ("FCFS", "AI"):
        r = run_policy(date, pol, trains, requests=df.copy())
        res[pol] = summarize(r)
    z = _z_opt_for(date, trains)
    cmp_ = compare(res["FCFS"], res["AI"], z or None)
    return {"date": date, "FCFS": res["FCFS"], "AI": res["AI"],
            "so_sanh": cmp_, "z_opt_offline": z}


# ---------------------------------------------------------------- report phase
def aggregate(jsonl: Path, out_json: Path, out_csv: Path):
    rows = [json.loads(x) for x in jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if not r.get("empty")]
    rows.sort(key=lambda r: r["date"])
    # Calendar contains event-marker rows on rollout dates; tau_tet is the same
    # for those duplicates, so keep one deterministic row per service date.
    cal = load_calendar().drop_duplicates("ngay", keep="first").set_index("ngay")

    daily = []
    for r in rows:
        f, a, c = r["FCFS"], r["AI"], r["so_sanh"]
        tt = int(cal.loc[r["date"], "tau_tet"]) if r["date"] in cal.index else 999
        daily.append({
            "date": r["date"], "tau_tet": tt, "is_tet": abs(tt) <= 21,
            "regime": "AI" if r["date"] >= "2026-05-01" else "LUAT",
            "dt_fcfs": f["doanh_thu"], "dt_ai": a["doanh_thu"],
            "tang_dt": c["tang_doanh_thu"], "tang_pax_km": c["tang_pax_km"],
            "tang_ve": c["tang_ve_ban"],
            "util_fcfs": f["he_so_su_dung_pax_km"], "util_ai": a["he_so_su_dung_pax_km"],
            "giam_ghe_trong": c["giam_ghe_trong_cuc_bo"],
            "giam_tu_choi": c["giam_tu_choi_unmet"],
            "gap_ghep_ai": a["so_gap_ghep_thanh_cong"],
            "het_cho_fcfs": f["ly_do_tu_choi"].get("HET_CHO", 0),
            "het_cho_ai": a["ly_do_tu_choi"].get("HET_CHO", 0),
            "bo_vi_gia_fcfs": f["ly_do_tu_choi"].get("BO_VI_GIA", 0),
            "bo_vi_gia_ai": a["ly_do_tu_choi"].get("BO_VI_GIA", 0),
            "ve_fcfs": f["so_ve_ban"], "ve_ai": a["so_ve_ban"],
            "gia_tren_F0_ai": a["gia_tren_F0_bq"], "p95_ms_ai": a["toc_do_tinh_lai_p95_ms"],
            "z_opt": r.get("z_opt_offline", 0),
            "eff_ai": c.get("hieu_suat_vs_toi_uu_offline"),
            "eff_fcfs": c.get("fcfs_vs_toi_uu_offline"),
        })
    d = pd.DataFrame(daily)
    d.to_csv(out_csv, index=False)

    def agg(sub: pd.DataFrame) -> dict:
        if not len(sub):
            return {}
        tot_f, tot_a = int(sub.dt_fcfs.sum()), int(sub.dt_ai.sum())
        return {
            "so_ngay": int(len(sub)),
            "tang_doanh_thu_tong": round(tot_a / tot_f - 1, 4),
            "tang_doanh_thu_median": round(float(sub.tang_dt.median()), 4),
            "tang_doanh_thu_min_max": [round(float(sub.tang_dt.min()), 4),
                                        round(float(sub.tang_dt.max()), 4)],
            "tang_pax_km_median": round(float(sub.tang_pax_km.median()), 4),
            "util_fcfs_bq": round(float(sub.util_fcfs.mean()), 4),
            "util_ai_bq": round(float(sub.util_ai.mean()), 4),
            "giam_ghe_trong_median": round(float(sub.giam_ghe_trong.median()), 4),
            "het_cho": {"fcfs": int(sub.het_cho_fcfs.sum()), "ai": int(sub.het_cho_ai.sum()),
                        "giam": round(1 - sub.het_cho_ai.sum() / max(sub.het_cho_fcfs.sum(), 1), 4)},
            "gap_ghep_tong": int(sub.gap_ghep_ai.sum()),
            "doanh_thu_tong": {"fcfs": tot_f, "ai": tot_a, "chenh": tot_a - tot_f},
            "gia_tren_F0_bq": round(float(sub.gia_tren_F0_ai.mean()), 4),
            "p95_ms_max": round(float(sub.p95_ms_ai.max()), 2),
        }

    fold = d[d.z_opt > 0]
    report = {
        "pham_vi": {"tu": d.date.min(), "den": d.date.max(), "so_ngay": int(len(d)),
                    "trains": "SE1,SE3,SE5,SE7"},
        "tong_hop_nam": agg(d),
        "theo_che_do": {"LUAT_truoc_2026-05-01": agg(d[d.regime == "LUAT"]),
                        "AI_sau_2026-05-01": agg(d[d.regime == "AI"])},
        "cao_diem_tet": agg(d[d.is_tet]),
        "ngay_thuong": agg(d[~d.is_tet]),
        "fold_co_optimum": {**agg(fold),
                            "hieu_suat_vs_z_opt": {
                                "ai_median": round(float(fold.eff_ai.median()), 4) if len(fold) else None,
                                "fcfs_median": round(float(fold.eff_fcfs.median()), 4) if len(fold) else None}},
        "theo_thang": {m: agg(g) for m, g in d.groupby(d.date.str[:7])},
    }
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[REPORT] {len(d)} ngày -> {out_json}\n[REPORT] minh chứng theo ngày -> {out_csv}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-07-01")
    ap.add_argument("--end", default="2026-06-30")
    ap.add_argument("--trains", default="SE1,SE3,SE5,SE7")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    trains = args.trains.split(",")
    cache_dir = Path(args.cache_dir)
    jsonl = cache_dir / "results.jsonl"
    dates = [d.strftime("%Y-%m-%d") for d in pd.date_range(args.start, args.end)]

    if not args.report_only:
        months = sorted({d[:7] for d in dates})
        build_cache(months, trains, cache_dir)

        done = set()
        if jsonl.exists():
            done = {json.loads(x)["date"] for x in jsonl.read_text(encoding="utf-8").splitlines() if x.strip()}
        todo = [d for d in dates if d not in done]
        print(f"[RUN] {len(todo)} ngày cần chạy ({len(done)} đã xong) | {args.workers} worker", flush=True)
        with ProcessPoolExecutor(max_workers=args.workers) as ex, \
             open(jsonl, "a", encoding="utf-8") as fh:
            futs = {ex.submit(run_one_date, (dt, trains, str(cache_dir))): dt for dt in todo}
            n = 0
            for fu in as_completed(futs):
                r = fu.result()
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                fh.flush()
                n += 1
                if n % 10 == 0 or n == len(todo):
                    print(f"[RUN] {n}/{len(todo)} ngày xong (mới nhất: {r['date']})", flush=True)

    aggregate(jsonl, ARTIFACTS / "backtest_year_report.json",
              ARTIFACTS / "backtest_year_daily.csv")


if __name__ == "__main__":
    main()

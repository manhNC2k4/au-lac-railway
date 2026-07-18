# -*- coding: utf-8 -*-
"""D3/D4 — Backtest Phase 1: AI vs FCFS vs trần tối ưu offline, xuất report.

Chạy:  python eval/backtest.py --dates 2026-02-14,2026-05-20 --trains SE1,SE3,SE5,SE7
Xuất:  models/artifacts/backtest_report.json
       models/artifacts/fill_matrix_<policy>_<date>.csv   (dữ liệu heatmap)
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ARTIFACTS, DATA
from eval.metrics import compare, summarize
from eval.replay import load_day, run_policy

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GT = DATA.parent / "_ground_truth"


def z_opt_for(date: str, trains: list[str]) -> int:
    opt = pd.read_parquet(GT / "offline_optimum.parquet")
    runs = [f"{t}_{date}" for t in trains]
    sel = opt[opt.chuyen_id.isin(runs)]
    return int(sel.z_opt.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", default="2026-02-14,2026-05-20")
    ap.add_argument("--trains", default="SE1,SE3,SE5,SE7")
    args = ap.parse_args()
    dates = args.dates.split(",")
    trains = args.trains.split(",")

    report = {"dates": dates, "trains": trains, "per_date": {}}
    for date in dates:
        print(f"\n===== BACKTEST {date} (tàu {','.join(trains)}) =====")
        reqs = load_day(date, trains)
        print(f"  yêu cầu replay: {len(reqs):,}")
        res = {}
        for pol in ("FCFS", "AI"):
            r = run_policy(date, pol, trains, requests=reqs.copy())
            s = summarize(r)
            res[pol] = s
            # xuất ma trận fill (heatmap data)
            fm = pd.DataFrame.from_dict(r["fill_matrix"], orient="index")
            fm.to_csv(ARTIFACTS / f"fill_matrix_{pol}_{date}.csv")
            print(f"  [{pol}] vé={s['so_ve_ban']:,} | DT={s['doanh_thu']:,}đ | "
                  f"pax-km util={s['he_so_su_dung_pax_km']:.3f} | "
                  f"gap ghép={s['so_gap_ghep_thanh_cong']} | đổi chỗ={s['ty_le_khach_doi_cho']:.2%} | "
                  f"từ chối={s['so_yeu_cau_tu_choi']:,} | p95={s['toc_do_tinh_lai_p95_ms']:.1f}ms")
        z = z_opt_for(date, trains)
        cmp_ = compare(res["FCFS"], res["AI"], z)
        print(f"  → AI vs FCFS: DT {cmp_['tang_doanh_thu']:+.1%} | pax-km {cmp_['tang_pax_km']:+.1%} | "
              f"vé {cmp_['tang_ve_ban']:+.1%} | ghế trống cục bộ {cmp_['giam_ghe_trong_cuc_bo']:+.1%} | "
              f"unmet {cmp_['giam_tu_choi_unmet']:+.1%}")
        if z:
            print(f"  → hiệu suất vs tối ưu offline (z_opt={z:,}): "
                  f"AI={cmp_.get('hieu_suat_vs_toi_uu_offline')} | FCFS={cmp_.get('fcfs_vs_toi_uu_offline')}")
        report["per_date"][date] = {"FCFS": res["FCFS"], "AI": res["AI"],
                                    "so_sanh": cmp_, "z_opt_offline": z}

    out = ARTIFACTS / "backtest_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Report -> {out}")


if __name__ == "__main__":
    main()

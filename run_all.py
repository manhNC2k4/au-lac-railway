# -*- coding: utf-8 -*-
"""CHẠY HOÀN CHỈNH 5 bài toán con end-to-end + xuất artifact + in output.

Kịch bản:
  A) Chế độ AI (2026-05-20, tàu SE7) — minh hoạ định giá động 2 chiều.
  B) Cao điểm Tết (2026-02-14, tàu SE1) — minh hoạ đoạn nghẽn + buộc ghép chặng.

Sinh artifact:
  models/artifacts/bt2_snapshot_<date>.npz + .meta.json   (Seat State Matrix)
  models/artifacts/bt3_allocation_<chuyen>.json           (LF + quota + bottleneck)
  models/artifacts/run_all_outputs.json                   (tổng hợp output 5 bài toán)
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.bt2_ssm import SeatStateMatrix
from app.bt3_allocation import analyze_run, load_factor_route
from app.bt4_merge import find_options
from app.bt5_pricing import Pricer
from app.config import ARTIFACTS, MACRO_CLASS, make_chuyen_id

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ARTIFACTS.mkdir(parents=True, exist_ok=True)
pricer = Pricer.load()
out = {}


def try_forecast():
    """BT1: nếu model đã train, dự báo 1 grain mẫu + đọc contract CSV."""
    try:
        from app.bt1_forecast import Forecaster
        fc = Forecaster.load()
    except Exception as e:
        print(f"[BT1] model chưa sẵn sàng ({e}); bỏ qua bước dự báo trực tiếp.")
        return None
    row = {"mac_tau": "SE7", "ga_di": "HNO", "ga_den": "DNA", "seat_class": "K4",
           "band": "trung", "dot_ban_ve": "THUONG", "che_do_gia": "AI", "dow": 2,
           "da_ban_truoc_u14": 120, "toc_do_ban_7d": 35, "cu_ly_km": 791.0,
           "tau_tet": 94, "la_le": 0, "H_horizon": 60, "sau_15_5": 1,
           "q_lag_7": 140, "rolling_mean_28": 150}
    yhat = fc.predict_one(row)
    metrics = fc.spec.get("metrics", {})
    print(f"[BT1] dự báo mẫu (SE7 HNO→DNA K4): {yhat:.2f} vé | metrics test={metrics}")
    return {"sample_forecast": round(yhat, 3), "metrics": metrics}


def scenario(ngay, mac_tau, filt, tier, ga_di, ga_den, uu_tien=False, label=""):
    print(f"\n{'='*70}\n{label}  [{mac_tau} {ngay}] {ga_di}→{ga_den} tier={tier} uu_tien={uu_tien}\n{'='*70}")
    ssm = SeatStateMatrix()
    ssm.build_date(ngay, filt)
    chuyen = make_chuyen_id(mac_tau, ngay)

    # BT2
    lf = ssm.load_factor(chuyen)
    print(f"[BT2] SSM {chuyen}: {ssm.get_segment_meta(chuyen).shape[0]} đoạn | "
          f"LF mean={lf.mean():.2f} min={lf.min():.2f} max={lf.max():.2f}")
    snap = ARTIFACTS / f"bt2_snapshot_{mac_tau}_{ngay}"
    ssm.save_snapshot(snap)

    # BT3
    a = analyze_run(ssm, pricer, chuyen)
    print(f"[BT3] LF_bq={a['lf_bq']} LF_max={a['lf_max']} | đoạn nghẽn={len(a['doan_nghen'])} "
          f"đoạn trống={len(a['doan_trong'])} | z_opt DLP={a['z_opt_dlp']:,}đ")
    if a["doan_nghen"]:
        print("      nghẽn:", [f"{d['ga_dau']}→{d['ga_cuoi']}({d['lf']})" for d in a["doan_nghen"][:4]])
    (ARTIFACTS / f"bt3_allocation_{mac_tau}_{ngay}.json").write_text(
        json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")

    # BT4
    macro = MACRO_CLASS.get(tier, tier)
    opt = find_options(ssm, chuyen, macro, ga_di, ga_den, uu_tien)
    print(f"[BT4] kha_thi={opt['kha_thi']} | {len(opt['phuong_an'])} phương án:")
    for o in opt["phuong_an"]:
        print(f"      #{o['rank']} {o['loai']:11s} đổi_chỗ={o['so_lan_doi_cho']} "
              f"ga_đổi={o['ga_doi']}  ({o.get('ghi_chu','')})")

    # BT5 (dùng LF + bid price hành trình từ BT3)
    lf_route = load_factor_route(ssm, chuyen, ga_di, ga_den,
                                 a["bid_price_theo_lop"], macro)
    from app.config import TIERS
    tier_full = tier if tier in pricer.varsigma else TIERS.get(macro, [tier])[0]
    ctx = {"che_do_gia": "AI" if ngay >= "2026-05-01" else "LUAT",
           "tau_tet": 94 if ngay >= "2026-05-01" else -3,
           "dot_ban_ve": "THUONG", "u": 10, "dow": 3, "la_le": False}
    q = pricer.quote(mac_tau, ga_di, ga_den, tier_full, ctx, lf_route)
    print(f"[BT5] F0={q.gia_goc_F0:,}đ → giá đề xuất={q.gia_de_xuat:,}đ | rules={q.rule_ids}")
    print(f"      giải thích: {q.giai_thich}")

    return {
        "ngay": ngay, "chuyen_id": chuyen, "ga_di": ga_di, "ga_den": ga_den, "tier": tier_full,
        "bt2_lf": {"mean": round(float(lf.mean()), 3), "min": round(float(lf.min()), 3),
                   "max": round(float(lf.max()), 3)},
        "bt3": {"lf_bq": a["lf_bq"], "so_doan_nghen": len(a["doan_nghen"]),
                "so_doan_trong": len(a["doan_trong"]), "z_opt_dlp": a["z_opt_dlp"]},
        "bt4_phuong_an": opt["phuong_an"],
        "bt5_dinh_gia": q.to_dict(),
    }


def demo_extras():
    """C2/C4/C5: tái phân bổ động, group seating, waitlist."""
    from app.bt1_forecast import DemandModel
    from app.contracts import BookingRequest, PassengerProfile
    from app.group_seating import plan_group
    from app.reallocation import propose_reallocation
    from app.waitlist import WaitlistManager
    print(f"\n{'='*70}\nC2/C4/C5 — realloc động · group seating · waitlist\n{'='*70}")
    ssm = SeatStateMatrix(); ssm.build_date("2026-05-20", ["SE7"])
    dm = DemandModel.load()
    row = {"mac_tau": "SE7", "ga_di": "HNO", "ga_den": "DNA", "seat_class": "K4",
           "band": "trung", "dot_ban_ve": "THUONG", "che_do_gia": "AI", "dow": 2,
           "da_ban_truoc_u14": 120, "toc_do_ban_7d": 35, "cu_ly_km": 791.0,
           "tau_tet": 94, "la_le": 0, "H_horizon": 60, "sau_15_5": 1,
           "q_lag_7": 140, "rolling_mean_28": 150}
    cid = make_chuyen_id("SE7", "2026-05-20")
    a, b = ssm.seg_range(cid, "HNO", "VIN")
    ssm.hold_with_expiry(cid, "NAM_K4", a, b, now_u=10, ttl_ngay=1)
    re_ = propose_reallocation(ssm, pricer, dm, cid,
                               {"trung": row}, {"trung": 60}, u=8.5)
    print(f"[C2] {re_['_log']['explain']}")
    gp = plan_group(ssm, cid, "NAM_K6", "HNO", "DNA", 5)
    print(f"[C4] {gp['plan']['ghi_chu']}")
    wm = WaitlistManager(pricer)
    wm.add(BookingRequest(cid, "HNO", "DNA", "NAM_K4", "2026-05-20", u=3), 50000)
    wm.add(BookingRequest(cid, "HNO", "VIN", "NGOI_MEM_DH", "2026-05-20", u=20,
                          profile=PassengerProfile(doi_tuong_csxh="HSSV", muc_giam_csxh=0.1)))
    m = wm.match(ssm)
    print(f"[C5] {m['_log']['explain']}")
    return {"c2": re_["_log"], "c4": gp["plan"], "c5": m["_log"]}


def main():
    out["bt1"] = try_forecast()
    out["scenario_A_AI"] = scenario("2026-05-20", "SE7", ["SE7"], "NAM_K4",
                                    "HNO", "DNA", False, "KỊCH BẢN A — chế độ AI (ghế đơn)")
    out["scenario_B_TET_merge"] = scenario("2026-02-14", "SE1", ["SE1"], "NGOI_MEM_DH",
                                           "HNO", "DNA", False, "KỊCH BẢN B — Tết: nghẽn + GHÉP CHẶNG")
    out["scenario_B_priority"] = scenario("2026-02-14", "SE1", ["SE1"], "NGOI_MEM_DH",
                                          "HNO", "DNA", True, "KỊCH BẢN B' — khách ưu tiên (loại ghép)")
    out["extras_c2_c4_c5"] = demo_extras()
    (ARTIFACTS / "run_all_outputs.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Tổng hợp output -> {ARTIFACTS/'run_all_outputs.json'}")
    print(f"✅ Artifact xuất tại: {ARTIFACTS}")


if __name__ == "__main__":
    main()

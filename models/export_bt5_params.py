# -*- coding: utf-8 -*-
"""Xuất tham số ĐỘNG CƠ GIÁ (bài toán 5) ra file model để FastAPI nạp.

Giá là RULE ENGINE khai báo (doc 03 §3: "pricing rules are declarative config, not
Python"). File này KHÔNG train ML — nó kết tinh các hằng số giá từ YAML + trains.csv
thành 1 artifact json duy nhất mà app/bt5_pricing.py nạp lại.

kappa0 hiệu chỉnh từ neo giá [THẬT] SE1 HN–SG ngồi mềm (giống generate_data.py) để
giá F0 khớp CHÍNH XÁC cột gia_goc trong dataset.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ARTIFACTS, DATA, SEAT_CLASSES, TIERS, YAML_PATH

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    r = yaml.safe_load(open(YAML_PATH, encoding="utf-8"))
    g = r["gia_co_ban"]
    theta = float(g["theta"])
    san = float(g["san_tran"]["san_ty_le_tren_F0"])
    tran = float(g["san_tran"]["tran_ty_le_tren_F0"])
    varsigma = {c["ma"]: float(c["varsigma"]) for c in r["loai_cho"]}

    # lý trình ga để tính d_full cho neo
    st = pd.read_csv(DATA / "stations.csv").set_index("ga_id")["ly_trinh_km"].to_dict()
    anchor = next(a for a in g["neo_kiem_tra"]
                  if a["mac_tau"] == "SE1" and a["loai_cho"] == "NGOI_MEM_DH")
    rho_se1 = next(m["rho_t"] for m in r["mac_tau"] if m["ma"] == "SE1")
    d_full = abs(st[anchor["od"][1]] - st[anchor["od"][0]])
    kappa0 = anchor["gia"] / (rho_se1 * 1.0 * d_full ** theta)   # varsigma_NGOI = 1.0

    # rho_t theo mọi mác tàu (kể cả SE30/HD... không có trong YAML) — lấy từ trains.csv
    tr = pd.read_csv(DATA / "trains.csv")
    rho_t = dict(zip(tr.mac_tau, tr.rho_t.astype(float)))

    ai = r["ai_gia_linh_hoat"]
    params = {
        "theta": theta,
        "kappa0": kappa0,
        "san_ty_le": san,
        "tran_ty_le": tran,
        "varsigma": varsigma,
        "tier_by_class": TIERS,
        "seat_classes": SEAT_CLASSES,
        "rho_t": rho_t,
        "km": st,
        "ai": {
            "hieu_luc_tu": str(ai["hieu_luc_tu"]),
            "bien_do": ai["bien_do"],
            "tran_theo_tuyen": ai["tran_theo_tuyen"],
            "kich_hoat": ai["dieu_kien_kich_hoat"],
        },
        "delta_mua": {"tet": 0.045, "he": 0.075},   # doc 01 §3.2
        "_source": "04_THAM_SO_CAU_HINH_MO_PHONG.yaml + trains.csv (neo SE1 HN-SG)",
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "bt5_pricing_params.json"
    out.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[BT5] kappa0={kappa0:,.2f} | theta={theta} | d_full(HNO-SGO)={d_full:.0f}km")
    print(f"[BT5] F0(SE1,HN-SG,NGOI_MEM_DH) = {rho_se1*1.0*kappa0*d_full**theta:,.0f} đ "
          f"(neo [THẬT] = {anchor['gia']:,} đ)")
    print(f"[BT5] xuất -> {out}")


if __name__ == "__main__":
    main()

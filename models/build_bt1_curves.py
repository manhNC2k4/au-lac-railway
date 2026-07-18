# -*- coding: utf-8 -*-
"""B1 — Ước lượng ĐƯỜNG CONG ĐẶT CHỖ F(u) từ dữ liệu, xuất artifact cho DemandModel.

F(u | band, tet) = tỷ lệ vé đã bán tại thời điểm u ngày trước khởi hành
                 = P(lead_time >= u), ước lượng theo (băng cự ly × cửa sổ Tết).
DemandModel dùng: remaining(u) = total × (1 − F(u));  unconstrain: total ≈ sold/F(u).

Xuất: artifacts/bt1_booking_curves.json  {band|tet: {u: F}}, lưới u = 0..120.
Chỉ dùng train period (< 01/5/2026) — tránh rò rỉ chế độ AI vào curve.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ARTIFACTS, BAND_EDGES, BAND_LABELS, DATA, REGIME_BREAK

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

U_GRID = list(range(0, 121))


def main():
    tx = pd.read_parquet(str(DATA / "transactions"),
                         columns=["ngay_chay", "cu_ly_km", "lead_time_ngay", "trang_thai"])
    tx = tx[(tx.trang_thai == "HIEU_LUC") & (tx.ngay_chay < REGIME_BREAK)]
    cal = pd.read_csv(DATA / "calendar_events.csv")
    cal = cal[pd.to_numeric(cal.tau_tet, errors="coerce").notna()]
    tet_days = set(cal[cal.tau_tet.astype(int).abs() <= 21].ngay)
    tx["is_tet"] = tx.ngay_chay.isin(tet_days)
    tx["band"] = pd.cut(tx.cu_ly_km, BAND_EDGES, labels=BAND_LABELS)

    curves = {}
    for (band, tet), g in tx.groupby(["band", "is_tet"], observed=True):
        lt = g.lead_time_ngay.values
        n = len(lt)
        F = [float((lt >= u).sum() / n) for u in U_GRID]     # đã bán TRƯỚC mốc u
        curves[f"{band}|{int(tet)}"] = F
        print(f"  {band}|tet={int(tet)}: n={n:,} | F(14)={F[14]:.3f} F(30)={F[30]:.3f}")

    out = {"u_grid": U_GRID, "curves": curves,
           "_source": f"transactions < {REGIME_BREAK} (train period)"}
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "bt1_booking_curves.json").write_text(
        json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"[B1] xuất -> {ARTIFACTS / 'bt1_booking_curves.json'}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""EDA dataset phục vụ 5 bài toán con demo (forecast / SSM / segment load / merge / pricing).
Chỉ ĐỌC data/, xuất bảng tóm tắt + (tùy chọn) hình PNG vào demo/eda_out/."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parents[1] / "generated_data"
OUT = Path(__file__).resolve().parent / "eda_out"
OUT.mkdir(exist_ok=True)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_PLT = True
except ImportError:
    HAS_PLT = False

COLS = ["ve_id", "mac_tau", "ngay_chay", "ga_di", "ga_den", "cu_ly_km", "loai_cho",
        "lead_time_ngay", "gia_niem_yet", "gia_cuoi", "che_do_gia", "so_lan_doi_cho",
        "trang_thai", "cho_so", "chuyen_id"]
tx = pd.read_parquet(str(BASE / "data" / "transactions"), columns=COLS)
tx["ngay_chay"] = pd.to_datetime(tx["ngay_chay"])
ok = tx[tx.trang_thai == "HIEU_LUC"].copy()
cal = pd.read_csv(BASE / "data" / "calendar_events.csv")
cal = cal[pd.to_numeric(cal.tau_tet, errors="coerce").notna()].copy()
cal["ngay"] = pd.to_datetime(cal["ngay"])
cal["tau_tet"] = cal["tau_tet"].astype(int)

print("=== EDA 1 — CẦU THEO NGÀY (input bài toán 1) ===")
daily = ok.groupby("ngay_chay").size().rename("ve")
d = daily.reset_index().merge(cal[["ngay", "tau_tet", "dow", "la_le"]],
                              left_on="ngay_chay", right_on="ngay")
print(f"Vé/ngày: mean={daily.mean():,.0f} | p5={daily.quantile(.05):,.0f} | p95={daily.quantile(.95):,.0f}")
print("Hệ số theo thứ (chuẩn hóa T2=1):")
dowf = d.groupby("dow").ve.mean()
print((dowf / dowf.iloc[0]).round(3).to_string())
tet_win = d[d.tau_tet.abs() <= 21].ve.mean() / d[d.tau_tet.abs() > 21].ve.mean()
print(f"Hệ số cầu cửa sổ Tết (|tau|<=21) so ngày thường: x{tet_win:.2f}")

print("\n=== EDA 2 — BOOKING CURVE THEO BĂNG CỰ LY (đặc trưng pickup u=14) ===")
band = pd.cut(ok.cu_ly_km, [0, 300, 900, 1800], labels=["ngan", "trung", "dai"])
pick = ok.assign(band=band).groupby("band", observed=True).apply(
    lambda g: pd.Series({
        "share_ban_truoc_u14": (g.lead_time_ngay >= 14).mean(),
        "lead_bq": g.lead_time_ngay.mean()}), include_groups=False)
print(pick.round(3).to_string())
print("→ pickup tại u=14 nắm phần lớn vé chặng dài, ít vé chặng ngắn ⇒ cần hệ số scale-up theo băng")

print("\n=== EDA 3 — TỰ TƯƠNG QUAN (giá trị lag cho forecast) ===")
top_od = ok.groupby(["ga_di", "ga_den"]).size().nlargest(5).index
for o, dd in top_od[:3]:
    s = ok[(ok.ga_di == o) & (ok.ga_den == dd)].groupby("ngay_chay").size()
    s = s.reindex(pd.date_range(s.index.min(), s.index.max()), fill_value=0)
    print(f"{o}->{dd}: autocorr lag7={s.autocorr(7):.2f} lag1={s.autocorr(1):.2f} (lag7 cao ⇒ q_lag_7 hữu ích)")

print("\n=== EDA 4 — THƯA THỚT GRAIN (chọn chỉ số đánh giá) ===")
g = ok.groupby(["mac_tau", "ga_di", "ga_den", "loai_cho", "ngay_chay"]).size()
print(f"Grain (tàu,O,D,loại chỗ,ngày): {len(g):,} ô có vé | trung vị vé/ô = {g.median():.0f} | tỷ lệ ô=1-2 vé: {(g<=2).mean():.0%}")
print("→ dữ liệu ĐẾM thưa ⇒ MASE/Poisson deviance, KHÔNG MAPE (đúng doc 02 §10.1)")

print("\n=== EDA 5 — LF THEO ĐOẠN (input bài toán 3 & 5) ===")
inv = pd.read_csv(BASE / "data" / "seat_inventory.csv")
lf_seg = inv.groupby("khu_gian_id").he_so_su_dung.mean()
print(f"LF BQ theo khu gian: min={lf_seg.min():.2f} (đoạn {lf_seg.idxmin()}) | max={lf_seg.max():.2f} (đoạn {lf_seg.idxmax()})")
print("Top 3 đoạn nghẽn:", lf_seg.nlargest(3).round(2).to_dict())
print("Top 3 đoạn trống:", lf_seg.nsmallest(3).round(2).to_dict())

print("\n=== EDA 6 — GAP & GHÉP CHẶNG (input bài toán 4) ===")
rs = pd.read_csv(BASE / "data" / "run_summary.csv")
print(f"Gap/chuyến: mean={rs.so_gap.mean():.0f} | p95={rs.so_gap.quantile(.95):.0f}")
print(f"Vé đổi chỗ: {(ok.so_lan_doi_cho > 0).sum():,} ({(ok.so_lan_doi_cho > 0).mean():.2%}) | phân bố M-1: "
      f"{ok[ok.so_lan_doi_cho>0].so_lan_doi_cho.value_counts().sort_index().to_dict()}")

print("\n=== EDA 7 — GIÁ THEO CHẾ ĐỘ (input bài toán 5) ===")
reg = ok.groupby("che_do_gia").agg(gia_bq=("gia_cuoi", "mean"), n=("ve_id", "size"))
print(reg.round(0).to_string())
ai = ok[ok.che_do_gia == "AI"]
print(f"Sau 01/5: vé AI chiếm {len(ai)/max(len(ok[ok.ngay_chay>='2026-05-01']),1):.1%} vé giai đoạn AI")

if HAS_PLT:
    fig, ax = plt.subplots(figsize=(12, 4))
    daily.plot(ax=ax, lw=0.7)
    ax.set_title("Vé/ngày 07/2025-06/2026 (đỉnh Tết quanh 17/02)")
    fig.savefig(OUT / "daily_demand.png", dpi=110, bbox_inches="tight")
    fig, ax = plt.subplots(figsize=(8, 4))
    for b, gr in ok.assign(band=band).groupby("band", observed=True):
        gr.lead_time_ngay.clip(0, 120).hist(bins=60, alpha=0.5, label=str(b), ax=ax, density=True)
    ax.legend(); ax.set_title("Booking curve theo băng cự ly")
    fig.savefig(OUT / "booking_curves.png", dpi=110, bbox_inches="tight")
    print(f"\nHình → {OUT}")
else:
    print("\n(matplotlib chưa cài — bỏ qua hình, bảng text đủ dùng)")

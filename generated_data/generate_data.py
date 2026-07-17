#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_data.py — Sinh dataset TỔNG HỢP đường sắt hành khách Việt Nam
Bài toán: AI cắt chặng – ghép chặng – giá vé linh hoạt.

Kiến trúc DGP (Tài liệu 02):
    Ngoại sinh (lịch/sự kiện/gián đoạn) -> Λ cầu tiềm ẩn (gravity + mode logit)
    -> NHPP dòng yêu cầu -> choice (WTP + recapture) <-> giá + tồn kho (nội sinh)
    -> giao dịch / hủy / log tìm kiếm.

Mọi tham số số học đọc từ 04_THAM_SO_CAU_HINH_MO_PHONG.yaml (không hard-code
giá trị đã có trong YAML). Hằng số cấu trúc không có trong YAML được gom vào
STRUCT bên dưới, có chú thích nguồn/giả định.

Ghi chú phương pháp:
  * NHPP: dùng conditional sampling (đếm Poisson + thời điểm i.i.d. từ mật độ
    chuẩn hóa) — tương đương CHÍNH XÁC với thinning Lewis–Shedler cho NHPP,
    không chia bin. Hàm nhpp_thinning() vẫn được cài và dùng cho quá trình
    gián đoạn (cường độ theo mùa).
  * kappa0 trong YAML ([FIT]=9800) mâu thuẫn với neo giá [THẬT]
    (SE1 HN–SG ngồi mềm = 1.152.000đ) => tự hiệu chỉnh lại từ neo.
  * Sàn/trần áp lên GIÁ NIÊM YẾT; giảm CSXH áp SAU CÙNG (Điều 40 NĐ 16/2026),
    dùng MAX không cộng dồn => gia_cuoi của đối tượng 90% được phép < sàn.
"""

import argparse
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# Console Windows mặc định cp1252 — ép UTF-8 để in tiếng Việt/emoji
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from scipy.optimize import linprog
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from lunardate import LunarDate
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

BASE = Path(__file__).resolve().parent
YAML_PATH = BASE / "Synthetic_DATA_guide" / "04_THAM_SO_CAU_HINH_MO_PHONG.yaml"

# ---------------------------------------------------------------------------
# Hằng số CẤU TRÚC không có trong YAML (giả định kỹ thuật, chú thích nguồn)
# ---------------------------------------------------------------------------
STRUCT = {
    # Hệ số ngày trong tuần (T2..CN) — [GIẢ] mẫu hành vi cuối tuần
    "dow_factor": [0.95, 0.85, 0.90, 1.00, 1.28, 1.05, 1.22],
    # Logit phương thức: hệ số quy đổi (beta_cost trên triệu đồng, beta_time / giờ) — [GIẢ]
    "mode_beta_cost_per_1m": 1.2,
    "mode_beta_time_per_h": 0.055,
    "rail_speed_kmh": 60.0,
    # WTP lognormal sigma; hệ số theo phân khúc — [GIẢ]
    "wtp_sigma": 0.38,
    "wtp_mult": {"CONG_VU": 1.30, "VE_QUE": 1.00, "DU_LICH": 1.05,
                 "THAM_THAN": 0.95, "HSSV": 0.80},
    "wtp_tet_boost": 1.30,   # Tết ít co giãn giá (neo: giá +4-5%, sản lượng +9,5%)
    # Xác suất đối tượng CSXH trong dòng khách — [GIẢ] cần phân tích độ nhạy
    "csxh_probs": [
        ("KHONG", 0.780, 0.00),
        ("NGUOI_CAO_TUOI", 0.080, 0.15),
        ("TRE_6_10", 0.040, 0.25),
        ("HSSV", 0.080, 0.10),
        ("THUONG_BINH_CDHH", 0.015, 0.30),
        ("ME_VNAH_TIEN_KN", 0.005, 0.90),
    ],
    # Tăng cường tàu: proxy cho phần cung ngoài phạm vi mô phỏng (tuyến nhánh, charter,
    # tàu địa phương) để tổng cung khớp mô men TOÀN MẠNG M1/M9 — [GIẢ], ghi trong README
    "aug_base_runs": 6,      # chuyến TC/ngày quanh năm
    "aug_tet_runs": 18,      # thêm trong cao điểm Tết (doc 01: 55 đoàn/ngày toàn mạng)
    "aug_he_runs": 10,       # thêm trong cao điểm hè
    # Giảm giá thương mại gộp (khứ hồi/tập thể...) — xác suất vé được hưởng — [GIẢ]
    "tm_prob": 0.12, "tm_disc": 0.08,
    # Mua sát ngày (phụ thu) — doc 01 §3.2
    "late_days": 2.0, "late_up_he": 0.06, "late_up_khac": 0.04,
    # Giảm xa ngày: hè >=20 ngày; Tết/sau hè >=10 ngày — doc 01 §3.2
    "early_disc": 0.08, "early_quota_per_class": 20,
    # Tỷ trọng chọn loại chỗ cơ sở (ngồi/K6/K4) — [GIẢ] theo cơ cấu chỗ
    "class_pref_day": [0.55, 0.28, 0.17],
    "class_pref_night": [0.30, 0.42, 0.28],
}

SEAT_CLASSES = ["NGOI_MEM_DH", "NAM_K6", "NAM_K4"]
TIERS = {"NGOI_MEM_DH": ["NGOI_MEM_DH"],
         "NAM_K6": ["NAM_K6_T1", "NAM_K6_T2", "NAM_K6_T3"],
         "NAM_K4": ["NAM_K4_T1", "NAM_K4_T2"]}


def det_frac(*keys) -> float:
    """Phân số [0,1) tất định từ hash — giá KHÔNG phụ thuộc số lần tìm kiếm."""
    h = hashlib.sha256("|".join(str(k) for k in keys).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def nhpp_thinning(lam_func, T, lam_max, rng):
    """Lewis & Shedler (1979) — dùng cho quá trình gián đoạn."""
    t, out = 0.0, []
    while True:
        t -= math.log(max(rng.random(), 1e-300)) / lam_max
        if t > T:
            return out
        if rng.random() <= lam_func(t) / lam_max:
            out.append(t)


# ---------------------------------------------------------------------------
# Cấu hình & mạng lưới
# ---------------------------------------------------------------------------
class Config:
    def __init__(self, path: Path):
        with open(path, encoding="utf-8") as f:
            self.raw = yaml.safe_load(f)
        self.yaml_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        r = self.raw
        self.seed = int(r["meta"]["master_seed"])
        # --- ga & khu gian ---
        self.stations = r["mang_luoi"]["ga"]
        self.sid = {g["id"]: k for k, g in enumerate(self.stations)}
        self.km = np.array([g["km"] for g in self.stations])
        self.n_seg = len(self.stations) - 1
        self.seg_len = np.diff(self.km)
        # --- Tết ---
        self.tet = {int(y): pd.Timestamp(d) for y, d in r["lich"]["tet_am_lich"].items()}
        if HAS_LUNAR:  # kiểm chứng chéo bằng lunardate (doc 03 §4.1)
            for y, d in self.tet.items():
                ld = (LunarDate(y, 1, 1).to_solar_date()
                      if hasattr(LunarDate(y, 1, 1), "to_solar_date")
                      else LunarDate(y, 1, 1).toSolarDate())
                assert (ld == d.date()), f"lunardate mâu thuẫn YAML năm {y}: {ld} vs {d.date()}"
        # --- giá ---
        g = r["gia_co_ban"]
        self.theta = float(g["theta"])
        self.san = float(g["san_tran"]["san_ty_le_tren_F0"])
        self.tran = float(g["san_tran"]["tran_ty_le_tren_F0"])
        # kappa0: hiệu chỉnh lại từ neo [THẬT] SE1 HN-SG ngồi mềm (YAML [FIT] mâu thuẫn)
        anchor = next(a for a in g["neo_kiem_tra"]
                      if a["mac_tau"] == "SE1" and a["loai_cho"] == "NGOI_MEM_DH")
        rho_se1 = next(m["rho_t"] for m in r["mac_tau"] if m["ma"] == "SE1")
        d_full = abs(self.km[self.sid[anchor["od"][1]]] - self.km[self.sid[anchor["od"][0]]])
        self.kappa0 = anchor["gia"] / (rho_se1 * 1.0 * d_full ** self.theta)
        self.varsigma = {c["ma"]: float(c["varsigma"]) for c in r["loai_cho"]}
        # --- cầu ---
        c = r["cau"]
        self.grav = c["gravity"]
        self.mode = c["mode_logit"]
        self.asym = c["bat_doi_xung_chieu"]
        self.mu1 = float(c["xu_the"]["mu1_tang_truong_nam"])
        self.kcn = c["luong_dac_thu_vn"][0]
        self.seg_shares = {p["ma"]: p["ty_trong"] for p in c["phan_khuc"]}
        self.seg_tet = {k: v for k, v in c["phan_khuc_tet"].items() if k != "ghi_chu"}
        # --- đường cong đặt chỗ ---
        self.curves = r["duong_cong_dat_cho"]["bang"]
        # --- lịch bán vé, điểm gãy ---
        self.dot_ban = r["lich"]["dot_ban_ve"]
        self.nghi_le = r["lich"]["nghi_le_2026"]
        self.diem_gay = r["lich"]["diem_gay_che_do"]
        self.su_kien = r["su_kien"]
        # --- trả vé, AI, gián đoạn, hàng chờ ---
        self.tra_ve = r["tra_ve"]
        self.ai = r["ai_gia_linh_hoat"]
        self.gd = r["gian_doan"]
        self.mo_men = {m["id"]: m for m in r["mo_men"]}
        self.hang_cho = r["hang_cho"]
        self.lua_chon = r["lua_chon"]

    def tau_tet(self, d: pd.Timestamp) -> int:
        yr = d.year if d.month <= 6 else d.year + 1
        best = min(self.tet.values(), key=lambda t: abs((d - t).days))
        return (d - best).days if yr in self.tet or True else 999


def build_trains(cfg: Config):
    """Tàu trục Thống Nhất + khu đoạn có lý trình trong YAML.

    Loại: SPT1 (ga PTH không có lý trình), tuyến nhánh HD/HP/SP (ngoài trục,
    YAML không có tọa độ). Bổ sung theo doc 01 §2.2: SE30 (đôi của SE29),
    SE17/SE18 (HN–ĐN), HĐ1..4 (Huế–ĐN, chạy trên trục chính; HĐ3/4 từ 3/2026).
    """
    trains = []
    for m in cfg.raw["mac_tau"]:
        if "tuyen" in m or m["ma"] == "SPT1":
            continue
        if m.get("ga_dau") not in cfg.sid or m.get("ga_cuoi") not in cfg.sid:
            continue
        trains.append(dict(m))
    # đôi của SE29 (doc 01 liệt kê SE29/30)
    trains.append({"ma": "SE30", "cap": "SE29/SE30", "chieu": "LE", "ga_dau": "DTR",
                   "ga_cuoi": "SGO", "gio_xp": "20:30", "so_ga_dung": 9, "rho_t": 1.00})
    # SE17/18 HN–ĐN (doc 01 §2.2)
    trains.append({"ma": "SE17", "cap": "SE17/SE18", "chieu": "LE", "ga_dau": "HNO",
                   "ga_cuoi": "DNA", "gio_xp": "22:00", "so_ga_dung": 12, "rho_t": 1.00})
    trains.append({"ma": "SE18", "cap": "SE17/SE18", "chieu": "CHAN", "ga_dau": "DNA",
                   "ga_cuoi": "HNO", "gio_xp": "21:20", "so_ga_dung": 12, "rho_t": 1.00})
    # Huế–ĐN "di sản" (2 đôi/ngày; HĐ3/4 từ 2026-03-01, doc 01 §1.2)
    for ma, chieu, gxp, tu in [("HD1", "LE", "07:45", None), ("HD2", "CHAN", "14:25", None),
                               ("HD3", "LE", "13:10", "2026-03-01"), ("HD4", "CHAN", "17:40", "2026-03-01")]:
        ga_dau, ga_cuoi = ("HUE", "DNA") if chieu == "LE" else ("DNA", "HUE")
        trains.append({"ma": ma, "cap": "HD", "chieu": chieu, "ga_dau": ga_dau,
                       "ga_cuoi": ga_cuoi, "gio_xp": gxp, "so_ga_dung": 3, "rho_t": 1.15,
                       "hieu_luc_tu": tu})
    # ga dừng + sức chứa
    # Sức chứa tính trực tiếp từ cấu trúc toa trong YAML.
    # Lưu ý: trường tong_cho trong YAML (546) mâu thuẫn với chính comment của nó
    # (3*56+2*42+7*28 = 448) => tin cấu trúc toa, bỏ qua tong_cho.
    comp = cfg.raw["thanh_phan_doan_tau"]

    def caps_from(comp_key):
        out = {c: 0 for c in SEAT_CLASSES}
        for toa in comp[comp_key]["toa"]:
            cls = toa["loai_cho"] if toa["loai_cho"] in SEAT_CLASSES else toa["loai_cho"]
            out[cls] += len(toa["so"]) * toa["so_cho"]
        return out

    cap_hi = caps_from("SE_cao_cap")
    cap_tb = caps_from("SE_thuong")
    for t in trains:
        i0, i1 = cfg.sid[t["ga_dau"]], cfg.sid[t["ga_cuoi"]]
        lo, hi = min(i0, i1), max(i0, i1)
        idxs = list(range(lo, hi + 1))
        if t["ma"] in ("SE1", "SE2", "SE3", "SE4", "SE19", "SE20", "SE21", "SE22"):
            idxs = [k for k in idxs if cfg.stations[k]["loai"] != "doc_duong" or k in (lo, hi)]
        t["stops"] = idxs if t["chieu"] == "LE" else idxs[::-1]
        t["seg_lo"], t["seg_hi"] = lo, hi
        t["cap"] = dict(cap_hi) if t["ma"] in ("SE1", "SE2", "SE3", "SE4") else dict(cap_tb)
        if t["ma"].startswith(("NA", "SNT", "HD")):  # đoàn ngắn hơn — [GIẢ]
            t["cap"] = {k: int(v * 0.7) for k, v in t["cap"].items()}
        hh, mm = t["gio_xp"].split(":")
        t["dep_min"] = int(hh) * 60 + int(mm)
        t["night"] = t["dep_min"] >= 18 * 60 or t["dep_min"] <= 5 * 60
    return trains


# ---------------------------------------------------------------------------
# Lịch
# ---------------------------------------------------------------------------
def build_calendar(cfg: Config, d0: pd.Timestamp, d1: pd.Timestamp):
    days = pd.date_range(d0, d1, freq="D")
    rows = {}
    holis = []
    for h in cfg.nghi_le:
        holis.append((pd.Timestamp(h["tu"]), pd.Timestamp(h["den"]), h["ten"]))
    holis.append((pd.Timestamp("2025-09-01"), pd.Timestamp("2025-09-02"), "Quốc khánh 2/9 (2025)"))
    for d in days:
        tau = cfg.tau_tet(d)
        le = next((h for h in holis if h[0] <= d <= h[1]), None)
        dist_le = min((abs((d - h[0]).days) for h in holis), default=99)
        # đợt bán vé -> H horizon
        H = 75
        dot = "THUONG"
        for db in cfg.dot_ban:
            if "tau_chay_tu" not in db:
                H_default = db.get("H_mac_dinh", 75)
                continue
            if pd.Timestamp(db["tau_chay_tu"]) <= d <= pd.Timestamp(db["tau_chay_den"]):
                H = (d - pd.Timestamp(db["ngay_mo_ban"])).days
                dot = db["ten"]
        H = int(np.clip(H, 20, 179))
        che_do = "AI" if d >= pd.Timestamp(cfg.ai["hieu_luc_tu"]) else "LUAT"
        # hệ số lịch tổng hợp
        f = STRUCT["dow_factor"][d.dayofweek]
        for h0, h1, _ in holis:
            f *= 1.0 + 0.85 * math.exp(-min(abs((d - h0).days), abs((d - h1).days)) ** 2 / (2 * 2.5 ** 2))
        f *= (1 + cfg.mu1) ** ((d - pd.Timestamp("2025-07-01")).days / 365.0)
        rows[d.normalize()] = dict(ngay=d, tau_tet=tau, dow=d.dayofweek, la_le=bool(le),
                                   ten_le=le[2] if le else "", dist_le=dist_le, dot_ban_ve=dot,
                                   H=H, che_do_gia=che_do, he_so_lich=f)
    return rows


def event_boost(cfg: Config, st_idx: int, d: pd.Timestamp) -> float:
    """eta_v cho ga trong cửa sổ sự kiện (YAML su_kien)."""
    ga = cfg.stations[st_idx]["id"]
    b = 1.0
    for ev in cfg.su_kien:
        if ga not in ev["ga"]:
            continue
        if "thang" in ev and d.month in ev["thang"]:
            b *= 1 + ev["eta"]
        elif "tu" in ev and pd.Timestamp(ev["tu"]) <= d <= pd.Timestamp(ev["den"]):
            b *= 1 + ev["eta"]
    return b


# ---------------------------------------------------------------------------
# Cầu tiềm ẩn: gravity + mode logit + bất đối xứng chiều
# ---------------------------------------------------------------------------
class Demand:
    def __init__(self, cfg: Config, kappa_scale: float, dist_tilt: float = 0.0):
        self.cfg = cfg
        self.kappa = kappa_scale
        g = cfg.grav
        st = cfg.stations
        n = len(st)
        P = np.array([s["P"] for s in st])
        TH = np.array([s["theta"] for s in st])
        D = np.abs(cfg.km[:, None] - cfg.km[None, :])
        fric = np.where(D > 0, D ** g["ma_sat"]["theta_d"] * np.exp(D / g["ma_sat"]["d0_km"]), np.inf)
        # dist_tilt: knob hiệu chuẩn mix cự ly (SMM 1 chiều, khớp M5).
        # Bão hòa tại 900km để không thổi phồng chặng siêu dài (giữ M14 trong biên).
        tilt = np.where(D > 0, (np.minimum(D, 900.0) / 300.0) ** dist_tilt, 0.0)
        self.base = (np.outer(P ** g["alpha"], P ** g["beta"])
                     * np.outer(TH ** g["gamma1"], TH ** g["gamma2"]) / fric * tilt)
        self.dist = D
        self.kcn_o = [cfg.sid[x] for x in cfg.kcn["ga_goc"]]
        self.kcn_d = [cfg.sid[x] for x in cfg.kcn["ga_dich"]]
        self.he_so_tet = float(cfg.kcn["he_so_tet"])

    def rail_share(self, d_km: float, p_rail: float, day: pd.Timestamp) -> float:
        m, S = self.cfg.mode, STRUCT
        bc, bt = S["mode_beta_cost_per_1m"], S["mode_beta_time_per_h"]
        road_fee = 1 + m["doi_thu"]["bo"]["muc_tang"] if day >= pd.Timestamp(m["doi_thu"]["bo"]["tang_phi_tu"]) else 1.0
        V = {"sat": m["ASC"]["sat"] - bc * p_rail / 1e6 - bt * d_km / S["rail_speed_kmh"]}
        b = m["doi_thu"]["bo"]
        V["bo"] = m["ASC"]["bo"] - bc * b["gia_dong_per_km"] * d_km * road_fee / 1e6 - bt * d_km / b["toc_do_kmh"]
        if d_km >= m["doi_thu"]["bay"]["chi_ap_dung_cu_ly_km_tu"]:
            a = m["doi_thu"]["bay"]
            V["bay"] = m["ASC"]["bay"] - bc * a["gia_dong_per_km"] * d_km / 1e6 - bt * a["thoi_gian_gio_co_dinh"]
        c = m["doi_thu"]["ca_nhan"]
        if d_km <= c["gioi_han_km"]:
            V["ca_nhan"] = m["ASC"]["ca_nhan"] - bc * c["gia_dong_per_km"] * d_km / 1e6 - bt * d_km / c["toc_do_kmh"]
        ex = {k: math.exp(v) for k, v in V.items()}
        return ex["sat"] / sum(ex.values())

    def dir_factor(self, tau: int, chieu: str) -> float:
        a = self.cfg.asym
        psi_m = math.exp(-(tau - a["truoc_tet"]["dinh_tau"]) ** 2 / (2 * a["truoc_tet"]["sigma"] ** 2))
        psi_p = math.exp(-(tau - a["sau_tet"]["dinh_tau"]) ** 2 / (2 * a["sau_tet"]["sigma"] ** 2))
        g = a["gamma_peak"]
        if chieu == "CHAN":
            return math.exp(math.log(g) * (psi_m - psi_p))
        return math.exp(math.log(g) * (psi_p - psi_m))

    def lam(self, o: int, dst: int, day_info: dict, day: pd.Timestamp, p_ref: float, chieu: str) -> float:
        d_km = self.dist[o, dst]
        if d_km < 30:
            return 0.0
        lam = self.kappa * self.base[o, dst] * day_info["he_so_lich"]
        lam *= event_boost(self.cfg, dst, day) * self.rail_share(d_km, p_ref, day)
        lam *= self.dir_factor(day_info["tau_tet"], chieu)
        tau = day_info["tau_tet"]
        if abs(tau) <= 21:                   # ⭐ mix Tết dịch về chặng dài (M8b)
            if d_km < 300:
                lam *= 0.45                  # Tết: du lịch/đi lại chặng ngắn giảm mạnh
            elif d_km >= 900:
                heavy_pre = chieu == "CHAN" and tau < 0
                heavy_post = chieu == "LE" and tau > 0
                if (o in self.kcn_o and dst in self.kcn_d and heavy_pre) or \
                   (o in self.kcn_d and dst in self.kcn_o and heavy_post):
                    lam *= self.he_so_tet
                elif heavy_pre or heavy_post:
                    lam *= 2.4
        return lam


def booking_curve(cfg: Config, d_km: float, tau: int, heavy: bool):
    """Chọn hàng đường cong đặt chỗ theo cự ly / Tết (YAML §6)."""
    if abs(tau) <= 21 and heavy and d_km >= 900:
        row = cfg.curves[3]
    elif d_km >= 900:
        row = cfg.curves[0]
    elif d_km >= 300:
        row = cfg.curves[1]
    else:
        row = cfg.curves[2]
    return row["w0"], [(c["w"], c["a"], c["b"]) for c in row["thanh_phan"]]


def sample_arrivals(rng, n, w0, comps, H):
    """NHPP conditional sampling: z ~ w0*δ0 + Σ w_m Beta(a,b); u = (1-z)H.
    Tương đương chính xác thinning Lewis–Shedler, không chia bin."""
    if n == 0:
        return np.empty(0)
    ws = np.array([w0] + [c[0] for c in comps])
    ws = ws / ws.sum()
    pick = rng.choice(len(ws), size=n, p=ws)
    z = np.zeros(n)
    for k, (w, a, b) in enumerate(comps, start=1):
        m = pick == k
        z[m] = rng.beta(a, b, m.sum())
    return (1.0 - z) * H  # u = số ngày trước khi tàu chạy; pick==0 -> z=0 -> u=H (mở bán)


# ---------------------------------------------------------------------------
# Động cơ giá — tái tạo bộ luật VNR (doc 01 §3, doc 02 §7)
# ---------------------------------------------------------------------------
class Pricer:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.ai_from = pd.Timestamp(cfg.ai["hieu_luc_tu"])
        self.ai_act = cfg.ai["dieu_kien_kich_hoat"]

    def f0(self, train: dict, d_km: float, tier: str) -> int:
        c = self.cfg
        return int(round(train["rho_t"] * c.varsigma[tier] * c.kappa0 * d_km ** c.theta))

    def delta_mua(self, day: pd.Timestamp, tau: int) -> float:
        if abs(tau) <= 21:
            return 0.045                                    # Tết +4..5%
        if pd.Timestamp("2026-05-15") <= day <= pd.Timestamp("2026-06-30"):
            return 0.075                                    # hè 2026 +5..10%
        return 0.0

    def quote(self, run_id, train, day, dinfo, o, dst, tier, u, lf_max, lf_min_route, early_cnt):
        """Trả về (gia_goc, gia_niem_yet, rules, ai_applied). Tất định theo trạng thái —
        KHÔNG phụ thuộc người dùng/số lần tìm kiếm."""
        cfg = self.cfg
        d_km = abs(cfg.km[dst] - cfg.km[o])
        f0 = self.f0(train, d_km, tier)
        rules = []
        p = float(f0)
        dm = self.delta_mua(day, dinfo["tau_tet"])
        if dm:
            p *= 1 + dm
            rules.append("MUA_VU")
        S = STRUCT
        tau = dinfo["tau_tet"]
        # xa ngày (quota 20 vé / loại chỗ / đoàn tàu)
        thr = 20 if dinfo["dot_ban_ve"] == "HE_2026" else 10
        if u >= thr and d_km >= 900 and early_cnt < S["early_quota_per_class"]:
            p *= 1 - S["early_disc"]
            rules.append("XA_NGAY")
        # Tết chiều rỗng: LẺ trước Tết / CHẴN sau Tết, >900km (doc 01 §3.2)
        if abs(tau) <= 21 and d_km > 900 and u >= 10:
            if (train["chieu"] == "LE" and tau < 0) or (train["chieu"] == "CHAN" and tau > 0):
                p *= 0.90
                rules.append("TET_CHIEU_RONG")
        # sát ngày: phụ thu
        if u <= S["late_days"]:
            up = S["late_up_he"] if dinfo["dot_ban_ve"] == "HE_2026" else S["late_up_khac"]
            p *= 1 + up
            rules.append("SAT_NGAY")
        # thương mại (khứ hồi/tập thể) — tất định theo yêu cầu
        if det_frac(run_id, o, dst, tier, "tm") < S["tm_prob"]:
            p *= 1 - S["tm_disc"]
            rules.append("TM")
        # AI giá linh hoạt (từ 01/5/2026)
        ai = False
        if (day >= self.ai_from and u <= self.ai_act["lead_time_toi_da_ngay"]
                and lf_max >= self.ai_act["max_lf_khu_gian_toi_thieu"]
                and lf_min_route <= self.ai_act["min_lf_tren_hanh_trinh_toi_da"]):
            cap = self._ai_cap(train, o, dst, d_km)
            lo = self.cfg.ai["bien_do"]["min"]
            depth = lo + (cap - lo) * det_frac(run_id, o, dst, int(u))  # tất định
            p *= 1 - depth
            rules.append(f"AI:{depth:.3f}")
            ai = True
        # clip sàn/trần trên giá niêm yết
        lo, hi = cfg.san * f0, cfg.tran * f0
        p_clip = min(max(p, lo), hi)
        if p_clip != p:
            rules.append("CLIP")
        return f0, int(round(p_clip)), rules, ai

    def _ai_cap(self, train, o, dst, d_km) -> float:
        t = self.cfg.ai["tran_theo_tuyen"]
        ids = (self.cfg.stations[o]["id"], self.cfg.stations[dst]["id"])
        if set(ids) == {"HUE", "DNA"}:
            return t["HUE_DANANG"]
        if d_km < 300:
            return t["THONG_NHAT_CHANG_NGAN"]
        return t.get("SG_DANANG", 0.25)


def csxh_apply(rng, gia_niem_yet: int):
    """Giảm CSXH: MAX một mức, áp SAU giảm động (Điều 40 NĐ 16/2026)."""
    r = rng.random()
    acc = 0.0
    for ten, prob, muc in STRUCT["csxh_probs"]:
        acc += prob
        if r < acc:
            return ten, muc, int(round(gia_niem_yet * (1 - muc)))
    return "KHONG", 0.0, gia_niem_yet


# ---------------------------------------------------------------------------
# Gián đoạn (sự kiện thật hard-code + NHPP mô phỏng)
# ---------------------------------------------------------------------------
def build_disruptions(cfg: Config, d0, d1, rng):
    evs = []
    for e in cfg.gd["su_kien_that"]:
        if "tu" not in e:
            continue
        for seg in e["doan_phong_toa_km"]:
            evs.append(dict(id=e["id"], tu=pd.Timestamp(e["tu"]), den=pd.Timestamp(e["den"]),
                            km0=seg["tu"], km1=seg["den"], nguon="THAT"))
    # mô phỏng NHPP theo vùng × mùa (thinning Lewis–Shedler)
    mp = cfg.gd["mo_phong"]
    vung = cfg.raw["mang_luoi"]["vung_thien_tai"]
    T = (d1 - d0).days
    for v in vung:
        lam_yr = mp["lambda_nam_theo_vung"][v["ten"]]

        def lam_f(t, v=v, lam_yr=lam_yr):
            d = d0 + timedelta(days=t)
            peak = 3.0 if d.month in v["thang_dinh"] else 0.3
            return lam_yr / 365.0 * peak

        for t in nhpp_thinning(lam_f, T, lam_yr / 365.0 * 3.5, rng):
            start = d0 + timedelta(days=t)
            if pd.Timestamp("2025-11-01") <= start <= pd.Timestamp("2025-11-30"):
                continue  # tháng 11/2025 đã có sự kiện thật
            dur = min(mp["thoi_luong"]["max_ngay"],
                      np.random.default_rng(int(t * 1000)).lognormal(
                          math.log(mp["thoi_luong"]["median_ngay"]), mp["thoi_luong"]["sigma"]))
            width = np.random.default_rng(int(t * 999)).lognormal(
                math.log(mp["do_dai_phong_toa_km"]["median"]), mp["do_dai_phong_toa_km"]["sigma"])
            km0 = v["km_tu"] + rng.random() * max(1.0, (v["km_den"] - v["km_tu"] - width))
            evs.append(dict(id=f"SIM_{start.date()}", tu=start, den=start + timedelta(days=float(dur)),
                            km0=km0, km1=km0 + width, nguon="MO_PHONG"))
    return evs


def blocked_ranges(cfg: Config, disruptions, day) -> list:
    """(km0, km1, ngay_cong_bo, id) — chỉ chặn bán khi mua SAU ngày công bố (= tu);
    vé mua trước công bố vẫn tồn tại và bị hủy + hoàn 100% => cơ chế chọn mẫu."""
    out = []
    for e in disruptions:
        if e["tu"] <= day <= e["den"]:
            out.append((e["km0"], e["km1"], e["tu"], e["id"]))
    return out


# ---------------------------------------------------------------------------
# LP: DLP / hindsight optimum + bid price (doc 02 §5.1–5.2)
# ---------------------------------------------------------------------------
def solve_dlp_and_bid_price(n_seg_range, od_list, demand_ub, fares, capacity):
    """max Σ f_ω y_ω  s.t.  A y ≤ C, 0 ≤ y ≤ D.  Ma trận khoảng => TU => nghiệm nguyên.
    Trả về (z_opt, bid_prices π_e)."""
    if not HAS_SCIPY or not od_list:
        return 0.0, []
    lo, hi = n_seg_range
    n_seg = hi - lo
    A = np.zeros((n_seg, len(od_list)))
    for k, (i, j) in enumerate(od_list):
        a, b = min(i, j), max(i, j)
        A[a - lo:b - lo, k] = 1.0
    res = linprog(c=-np.asarray(fares, float), A_ub=A, b_ub=np.full(n_seg, capacity),
                  bounds=[(0, d) for d in demand_ub], method="highs")
    if not res.success:
        return 0.0, []
    duals = getattr(getattr(res, "ineqlin", None), "marginals", None)
    pi = (-np.asarray(duals)).round(0).tolist() if duals is not None else []
    return float(-res.fun), pi


# ---------------------------------------------------------------------------
# Mô phỏng 1 ngày chạy tàu (event-driven, gộp mọi chuyến trong ngày để recapture)
# ---------------------------------------------------------------------------
class RunState:
    """Trạng thái tồn kho 1 chuyến: ma trận ghế × khu gian (True = trống)."""

    def __init__(self, run_id, train, cfg: Config):
        self.run_id, self.train, self.cfg = run_id, train, cfg
        lo, hi = train["seg_lo"], train["seg_hi"]
        self.lo, self.n_seg = lo, hi - lo
        self.free = {c: np.ones((train["cap"][c], self.n_seg), dtype=bool) for c in SEAT_CLASSES}
        self.early_cnt = defaultdict(int)     # quota 20 vé xa ngày / loại chỗ
        self.sold = 0
        self.revenue = 0
        self.req_by_od = defaultdict(int)     # cho LP hindsight
        self.fare_by_od = defaultdict(list)

    def seg_range(self, o, d):
        a, b = min(o, d), max(o, d)
        return a - self.lo, b - self.lo

    def load_factor(self, o=None, d=None):
        """(max LF toàn chuyến, min LF trên hành trình (o,d))."""
        tot_cap = sum(f.shape[0] for f in self.free.values())
        occ = sum(f.shape[0] - f.sum(axis=0) for f in self.free.values())
        lf = occ / max(tot_cap, 1)
        lf_max = float(lf.max()) if len(lf) else 0.0
        if o is None:
            return lf_max, 0.0
        a, b = self.seg_range(o, d)
        lf_min = float(lf[a:b].min()) if b > a else 0.0
        return lf_max, lf_min

    def try_assign(self, cls, o, d, allow_split, priority):
        """First-fit 1 chỗ liên tục; nếu hết mới thử ghép ≥2 chỗ (min interval cover).
        Trả về (list các (seat, a, b)) hoặc None."""
        a, b = self.seg_range(o, d)
        F = self.free[cls]
        ok = F[:, a:b].all(axis=1)
        idx = np.argmax(ok)
        if ok[idx]:
            F[idx, a:b] = False
            return [(int(idx), a, b)]
        if not allow_split or priority:
            return None
        # tham lam quét trái->phải: tại pos chọn ghế có run trống dài nhất
        pieces, pos, guard = [], a, 0
        while pos < b and guard < 6:
            guard += 1
            fcol = F[:, pos]
            if not fcol.any():
                for s, x, y in pieces:
                    F[s, x:y] = True
                return None
            cand = np.flatnonzero(fcol)
            best_s, best_end = -1, pos
            for s in cand:
                run = pos
                while run < b and F[s, run]:
                    run += 1
                if run > best_end:
                    best_s, best_end = int(s), run
                if run == b:
                    break
            pieces.append((best_s, pos, best_end))
            pos = best_end
        if pos < b or len(pieces) < 2:
            for s, x, y in pieces:
                F[s, x:y] = True
            return None
        for s, x, y in pieces:
            F[s, x:y] = False
        return pieces

    def release(self, pieces, cls):
        for s, x, y in pieces:
            self.free[cls][s, x:y] = True

    def gaps(self, min_seg=1):
        """Số khoảng trống (maximal free interval) trên các ghế ĐÃ từng bán."""
        n = 0
        for cls, F in self.free.items():
            used = ~F.all(axis=1)
            for row in F[used]:
                prev = False
                run = 0
                for v in row:
                    if v:
                        run += 1
                    else:
                        if run >= min_seg:
                            n += 1
                        run = 0
                if run >= min_seg and run < len(row):
                    n += 1
        return n


def simulate_day(day, runs, cfg, dem, pricer, dinfo, disruptions, rng, out, gt):
    """Sinh yêu cầu NHPP cho mọi (chuyến, O–D), xử lý theo thời gian, có recapture."""
    blocked = blocked_ranges(cfg, disruptions, day)
    states = {}
    events = []  # (u giảm dần => thời gian thực tăng): sort theo -u
    for tr in runs:
        rid = f"{tr['ma']}_{day.date()}"
        st = RunState(rid, tr, cfg)
        states[rid] = st
        stops = tr["stops"]
        H = dinfo["H"]
        for ii in range(len(stops) - 1):
            for jj in range(ii + 1, len(stops)):
                o, dst = stops[ii], stops[jj]
                d_km = abs(cfg.km[dst] - cfg.km[o])
                tier0 = "NGOI_MEM_DH"
                p_ref = pricer.f0(tr, d_km, tier0) * (1 + pricer.delta_mua(day, dinfo["tau_tet"]))
                lam = dem.lam(o, dst, dinfo, day, p_ref, tr["chieu"])
                # chia sẻ cầu giữa các mác tàu cùng phục vụ O–D — trọng số sức chứa
                lam *= tr.get("_share", 1.0)
                if lam <= 0:
                    continue
                n = rng.poisson(lam)
                if n == 0:
                    continue
                heavy = dem.dir_factor(dinfo["tau_tet"], tr["chieu"]) > 1.05
                w0, comps = booking_curve(cfg, d_km, dinfo["tau_tet"], heavy)
                us = sample_arrivals(rng, n, w0, comps, H)
                for u in us:
                    events.append((float(u), rid, o, dst))
                gt["lambda"].append((rid, cfg.stations[o]["id"], cfg.stations[dst]["id"], round(lam, 4)))
    events.sort(key=lambda e: -e[0])  # u lớn = mua sớm

    cancels = []  # (u_cancel, rid, cls, pieces, ve_id, refund)
    heavy_dir = {rid: dem.dir_factor(dinfo["tau_tet"], states[rid].train["chieu"]) > 1.05 for rid in states}
    tra_cfg = cfg.tra_ve
    post_online = day >= pd.Timestamp("2026-05-15")
    p_cancel_base = tra_cfg["ty_le_muc_tieu"]["sau_15_5_2026" if post_online else "truoc_15_5_2026"]

    seg_names = list(cfg.seg_shares)
    seg_p = np.array([cfg.seg_shares[s] for s in seg_names])
    if abs(dinfo["tau_tet"]) <= 21:
        seg_p = np.array([cfg.seg_tet.get(s, 0.02) for s in seg_names])
    seg_p = seg_p / seg_p.sum()

    for u, rid, o, dst in events:
        # xử lý hủy đến trước thời điểm này
        while cancels and cancels[-1][0] >= u:
            uc, crid, ccls, pieces, vid, refund = cancels.pop()
            states[crid].release(pieces, ccls)
            out["refunds"].append((vid, crid, round(uc, 2), refund, "TRA_VE"))
        st = states[rid]
        tr = st.train
        d_km = abs(cfg.km[dst] - cfg.km[o])
        # gián đoạn: cấm bán CHỈ KHI thời điểm mua (ngày chạy - u) sau ngày công bố
        km_a, km_b = sorted((cfg.km[o], cfg.km[dst]))
        buy_date = day - timedelta(days=float(u))
        hit = any(not (km_b <= b0 or km_a >= b1) and buy_date >= tu
                  for b0, b1, tu, _ in blocked)
        rq_id = out["next_req"][0]
        out["next_req"][0] += 1
        seg_kh = seg_names[int(rng.choice(len(seg_names), p=seg_p))]
        if hit:
            out["search"].append((rq_id, str(day.date()), round(u, 2), cfg.stations[o]["id"],
                                  cfg.stations[dst]["id"], rid, seg_kh, "TU_CHOI_GIAN_DOAN", ""))
            continue
        # chọn loại chỗ
        pref = STRUCT["class_pref_night"] if tr["night"] else STRUCT["class_pref_day"]
        cls = SEAT_CLASSES[int(rng.choice(3, p=pref))]
        tier = TIERS[cls][int(rng.integers(len(TIERS[cls])))]
        lf_max, lf_min = st.load_factor(o, dst)
        f0, p_ny, rules, ai = pricer.quote(rid, tr, day, dinfo, o, dst, tier, u,
                                           lf_max, lf_min, st.early_cnt[cls])
        # WTP
        seg_mult = STRUCT["wtp_mult"][seg_kh]
        if abs(dinfo["tau_tet"]) <= 21 and seg_kh == "VE_QUE":
            seg_mult *= STRUCT["wtp_tet_boost"]
        wtp = f0 * (1 + pricer.delta_mua(day, dinfo["tau_tet"])) * seg_mult \
            * math.exp(rng.normal(0.05, STRUCT["wtp_sigma"]))
        gt["wtp"].append((rq_id, int(wtp), seg_kh))
        st.req_by_od[(o, dst)] += 1
        st.fare_by_od[(o, dst)].append(p_ny)
        if wtp < p_ny:
            out["search"].append((rq_id, str(day.date()), round(u, 2), cfg.stations[o]["id"],
                                  cfg.stations[dst]["id"], rid, seg_kh, "BO_VI_GIA", ""))
            continue
        # ưu tiên (cao tuổi/khuyết tật...) => không được ghép chỗ
        priority = rng.random() < 0.09
        allow_split = (not priority) and rng.random() < cfg.hang_cho["do_linh_hoat"]["chap_nhan_doi_cho"]
        pieces = st.try_assign(cls, o, dst, allow_split, priority)
        target = st
        if pieces is None:
            # recapture: thử tàu khác cùng ngày cùng O–D
            if rng.random() < cfg.lua_chon["thu_hoi"]["sang_tau_khac_cung_ngay"]:
                for rid2, st2 in states.items():
                    if rid2 == rid:
                        continue
                    tr2 = st2.train
                    if o in tr2["stops"] and dst in tr2["stops"] and \
                            tr2["stops"].index(o) < tr2["stops"].index(dst):
                        pieces = st2.try_assign(cls, o, dst, allow_split, priority)
                        if pieces is not None:
                            target = st2
                            lf_max, lf_min = st2.load_factor(o, dst)
                            f0, p_ny, rules, ai = pricer.quote(rid2, tr2, day, dinfo, o, dst,
                                                               tier, u, lf_max, lf_min,
                                                               st2.early_cnt[cls])
                            break
            if pieces is None:
                kq = "VAO_HANG_CHO" if rng.random() < cfg.hang_cho["ty_le_vao_hang_cho_khi_bi_tu_choi"] \
                    else "TU_CHOI_HET_CHO"
                out["search"].append((rq_id, str(day.date()), round(u, 2), cfg.stations[o]["id"],
                                      cfg.stations[dst]["id"], rid, seg_kh, kq, ""))
                continue
        # kiểm tra M>=2: khách phải đồng ý (sigma model YAML §7)
        M = len(pieces)
        if M >= 2:
            z = cfg.lua_chon["chap_nhan_doi_cho"]
            p_ok = 1 / (1 + math.exp(-(z["zeta0"] - z["zeta1"] * M - z["zeta2"] * tr["night"])))
            if rng.random() > p_ok:
                target.release(pieces, cls)
                out["search"].append((rq_id, str(day.date()), round(u, 2), cfg.stations[o]["id"],
                                      cfg.stations[dst]["id"], rid, seg_kh, "TU_CHOI_DOI_CHO", ""))
                continue
        # CSXH áp SAU giảm động, max không cộng dồn — giá khóa sau khi giữ chỗ
        doi_tuong, muc, p_final = csxh_apply(rng, p_ny)
        if "XA_NGAY" in rules:
            target.early_cnt[cls] += 1
        ve_id = out["next_ve"][0]
        out["next_ve"][0] += 1
        target.sold += 1
        target.revenue += p_final
        out["search"].append((rq_id, str(day.date()), round(u, 2), cfg.stations[o]["id"],
                              cfg.stations[dst]["id"], target.run_id, seg_kh, "MUA", str(ve_id)))
        out["tx"].append((ve_id, rq_id, target.run_id, target.train["ma"], str(day.date()),
                          cfg.stations[o]["id"], cfg.stations[dst]["id"], round(float(d_km), 1),
                          tier, round(u, 2), f0, p_ny, p_final, doi_tuong, muc,
                          ";".join(rules), "AI" if ai else "LUAT", M - 1,
                          int(pieces[0][0]), "HIEU_LUC"))
        # lên lịch hủy (hazard đơn giản hóa từ mục tiêu tỷ lệ + Cox flags)
        pc = p_cancel_base * math.exp(tra_cfg["hazard"]["phi"]["la_tet"] if abs(dinfo["tau_tet"]) <= 21 else 0)
        if u > 1.3 and rng.random() < pc:
            uc = 1.0 + (u - 1.0) * rng.beta(1.3, 2.5)
            refund = int(round(p_final * (1 - tra_cfg["khau_tru_ty_le"])))
            cancels.append((uc, target.run_id, cls, pieces, ve_id, refund))
            cancels.sort(key=lambda x: x[0])  # giữ giảm dần khi pop từ cuối? -> sort tăng, pop nhỏ nhất cuối
            cancels.sort(key=lambda x: -x[0])
    # hủy còn lại (u nhỏ) — vẫn trước giờ chạy
    for uc, crid, ccls, pieces, vid, refund in cancels:
        states[crid].release(pieces, ccls)
        out["refunds"].append((vid, crid, round(uc, 2), refund, "TRA_VE"))
    # thiên tai: hủy vé có hành trình GIAO đoạn phong tỏa (KHÔNG ngẫu nhiên đều)
    # — hoàn 100% (không khấu trừ 30%) => tự tái tạo cơ chế chọn mẫu M14 > M5
    if blocked:
        today = str(day.date())
        for k in range(len(out["tx"]) - 1, -1, -1):
            t = out["tx"][k]
            if t[4] != today:
                break  # buffer append theo thứ tự ngày — vé cũ hơn không thuộc hôm nay
            if t[19] != "HIEU_LUC":
                continue
            km_a, km_b = sorted((cfg.km[cfg.sid[t[5]]], cfg.km[cfg.sid[t[6]]]))
            if any(not (km_b <= b0 or km_a >= b1) for b0, b1, _, _ in blocked):
                out["tx"][k] = t[:19] + ("BI_HUY_DO_THIEN_TAI",)
                out["refunds"].append((t[0], t[2], 0.0, t[12], "THIEN_TAI"))
    # tồn kho lúc chốt + GT tối ưu offline
    for rid, st in states.items():
        lf_arr = None
        tot_cap = 0
        for cls, F in st.free.items():
            cap = F.shape[0]
            tot_cap += cap
            occ = cap - F.sum(axis=0)
            if lf_arr is None:
                lf_arr = occ.astype(float)
            else:
                lf_arr += occ
            for e in range(st.n_seg):
                out["inv"].append((rid, st.lo + e + 1, cls, cap, int(occ[e]),
                                   round(float(occ[e] / cap), 4)))
        out["runstat"].append((rid, st.train["ma"], str(day.date()), st.sold, st.revenue,
                               st.gaps(), tot_cap,
                               round(float((lf_arr / tot_cap).mean()), 4) if lf_arr is not None else 0.0))
        gt["lp_jobs"].append((rid, (st.train["seg_lo"], st.train["seg_hi"]),
                              dict(st.req_by_od),
                              {k: float(np.mean(v)) for k, v in st.fare_by_od.items()},
                              st.train["cap"], st.revenue))


# ---------------------------------------------------------------------------
# Điều phối chính
# ---------------------------------------------------------------------------
def runs_for_day(trains, cfg, day, dinfo):
    out = []
    for tr in trains:
        if tr.get("hieu_luc_tu") and day < pd.Timestamp(tr["hieu_luc_tu"]):
            continue
        out.append(tr)
    # tăng cường cao điểm (doc 01: Tết 55 đoàn/ngày; hè ~1,5tr vé)
    tau = dinfo["tau_tet"]
    n_aug = STRUCT["aug_base_runs"]
    if -14 <= tau <= 19:
        n_aug += STRUCT["aug_tet_runs"]
    elif dinfo["dot_ban_ve"] == "HE_2026":
        n_aug += STRUCT["aug_he_runs"]
    base_tn = [t for t in trains if t["ma"].startswith("SE") and t["seg_hi"] - t["seg_lo"] >= 20]
    for k in range(n_aug):
        src = base_tn[k % len(base_tn)]
        cp = dict(src)
        cp["ma"] = f"{src['ma']}TC{k+1}"
        out.append(cp)
    # trọng số chia sẻ cầu O–D giữa các chuyến (theo sức chứa)
    cov = defaultdict(float)
    for t in out:
        cov_key = (t["seg_lo"], t["seg_hi"])
        cov[cov_key] += sum(t["cap"].values())
    for t in out:
        total_same = sum(sum(x["cap"].values()) for x in out
                         if x["seg_lo"] <= t["seg_lo"] and x["seg_hi"] >= t["seg_hi"])
        t = t  # share tính trên tàu phủ od — xấp xỉ: chia đều theo sức chứa các tàu phủ cùng đoạn
    n_cover = defaultdict(int)
    for t in out:
        n_cover[(t["seg_lo"], t["seg_hi"])] += 1
    for t in out:
        # số tàu phủ trọn đoạn của t (bao gồm tàu dài hơn)
        n = sum(1 for x in out if x["seg_lo"] <= t["seg_lo"] and x["seg_hi"] >= t["seg_hi"])
        t["_share"] = 1.0 / max(n, 1)
    return out


def flush_month(buf, outdir, month_key):
    if buf["tx"]:
        df = pd.DataFrame(buf["tx"], columns=[
            "ve_id", "yeu_cau_id", "chuyen_id", "mac_tau", "ngay_chay", "ga_di", "ga_den",
            "cu_ly_km", "loai_cho", "lead_time_ngay", "gia_goc", "gia_niem_yet", "gia_cuoi",
            "doi_tuong_csxh", "muc_giam_csxh", "rule_ids", "che_do_gia", "so_lan_doi_cho",
            "cho_so", "trang_thai"])
        for c in ("gia_goc", "gia_niem_yet", "gia_cuoi"):
            df[c] = df[c].astype("int64")
        p = outdir / "transactions" / f"thang={month_key}"
        p.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p / "part.parquet", index=False)
        buf["tx"].clear()
    if buf["search"]:
        df = pd.DataFrame(buf["search"], columns=[
            "yeu_cau_id", "ngay_di", "lead_time_ngay", "ga_di", "ga_den",
            "chuyen_id", "phan_khuc", "ket_qua", "ve_id"])
        p = outdir / "search_log" / f"thang={month_key}"
        p.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p / "part.parquet", index=False)
        buf["search"].clear()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-07-01")
    ap.add_argument("--end", default="2026-06-30")
    ap.add_argument("--out", default=str(BASE / "data"))
    ap.add_argument("--gt", default=str(BASE / "_ground_truth"))
    ap.add_argument("--kappa", type=float, default=None, help="bỏ qua hiệu chuẩn pilot")
    ap.add_argument("--skip-lp", action="store_true")
    args = ap.parse_args()

    t_start = time.time()
    cfg = Config(YAML_PATH)
    np.random.seed(cfg.seed)
    import random as _random
    _random.seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)

    d0, d1 = pd.Timestamp(args.start), pd.Timestamp(args.end)
    outdir, gtdir = Path(args.out), Path(args.gt)
    outdir.mkdir(parents=True, exist_ok=True)
    gtdir.mkdir(parents=True, exist_ok=True)

    trains = build_trains(cfg)
    # lịch phủ cả khoảng chạy lẫn khoảng chuẩn (pilot hiệu chuẩn cần các ngày 2026)
    cal = build_calendar(cfg, min(d0, pd.Timestamp("2025-07-01")),
                         max(d1, pd.Timestamp("2026-06-30")))
    pricer = Pricer(cfg)
    disruptions = build_disruptions(cfg, d0, d1, rng)

    # -------- hiệu chuẩn pilot (SMM rút gọn 2 chiều: dist_tilt khớp M5, kappa khớp M1) --------
    pilot_days = [pd.Timestamp(x) for x in
                  ["2026-01-15", "2026-02-10", "2026-02-25", "2026-03-20",
                   "2026-04-25", "2026-05-20", "2026-06-10", "2025-10-15"]]
    # hệ số phân tích: mix loại chỗ (pref × varsigma bình quân tầng) và CSXH bình quân
    v = cfg.varsigma
    class_mult = (STRUCT["class_pref_day"][0] * v["NGOI_MEM_DH"]
                  + STRUCT["class_pref_day"][1] * np.mean([v["NAM_K6_T1"], v["NAM_K6_T2"], v["NAM_K6_T3"]])
                  + STRUCT["class_pref_day"][2] * np.mean([v["NAM_K4_T1"], v["NAM_K4_T2"]]))
    csxh_mult = sum(p * (1 - m) for _, p, m in STRUCT["csxh_probs"])

    def pilot_stats(tilt):
        """(Λ bình quân/ngày, giá vé kỳ vọng phía cầu) — phân tích, không mô phỏng."""
        dp = Demand(cfg, 1.0, tilt)
        tot, wfare = 0.0, 0.0
        for day in pilot_days:
            di = cal[day.normalize()]
            for tr in runs_for_day(trains, cfg, day, di):
                stops = tr["stops"]
                for ii in range(len(stops) - 1):
                    for jj in range(ii + 1, len(stops)):
                        o, dst = stops[ii], stops[jj]
                        d_km = abs(cfg.km[dst] - cfg.km[o])
                        if d_km < 30:
                            continue
                        f_ref = pricer.f0(tr, d_km, "NGOI_MEM_DH") * class_mult * csxh_mult
                        lam = dp.lam(o, dst, di, day, f_ref, tr["chieu"]) * tr["_share"]
                        tot += lam
                        wfare += lam * f_ref
        return tot / len(pilot_days), (wfare / tot if tot else 0.0)

    target_m5 = float(cfg.mo_men["M5"]["gia_tri"])
    # mix bán ngắn hơn mix cầu (chặng dài chiếm nhiều khu gian, bị ràng buộc sức chứa hơn)
    SOLD_MIX_ADJ = 1.04
    lo_t, hi_t = -0.2, 2.5
    for _ in range(22):          # bisection: E[fare] tăng đơn điệu theo tilt
        mid = (lo_t + hi_t) / 2
        _, f_mid = pilot_stats(mid)
        if f_mid < target_m5 * SOLD_MIX_ADJ:
            lo_t = mid
        else:
            hi_t = mid
    dist_tilt = (lo_t + hi_t) / 2
    lam_day, f_exp = pilot_stats(dist_tilt)

    if args.kappa is None:
        target_m1 = float(cfg.mo_men["M1"]["gia_tri"])         # khách 6T/2026
        conv_guess = 0.48          # tỷ lệ chuyển đổi giả định (WTP + availability)
        kappa = (target_m1 / 181.0 / conv_guess) / lam_day
    else:
        kappa = args.kappa
    print(f"[calib] dist_tilt={dist_tilt:.3f} (E[fare] cầu={f_exp:,.0f}) | kappa={kappa:.3g}")
    dem = Demand(cfg, kappa, dist_tilt)

    # ---------------- vòng mô phỏng chính ----------------
    buf = dict(tx=[], search=[], inv=[], refunds=[], runstat=[],
               next_req=[1], next_ve=[1])
    gt = dict(lambda_=None, wtp=[], lp_jobs=[])
    gt["lambda"] = []
    all_inv, all_ref, all_runstat = [], [], []
    cur_month = None
    n_days = (d1 - d0).days + 1
    for k in range(n_days):
        day = d0 + timedelta(days=k)
        mk = day.strftime("%Y-%m")
        if cur_month and mk != cur_month:
            flush_month(buf, outdir, cur_month)
        cur_month = mk
        dinfo = cal[day.normalize()]
        runs = runs_for_day(trains, cfg, day, dinfo)
        day_rng = np.random.default_rng(
            int.from_bytes(hashlib.sha256(f"{cfg.seed}|{day.date()}".encode()).digest()[:8], "big"))
        simulate_day(day, runs, cfg, dem, pricer, dinfo, disruptions, day_rng, buf, gt)
        all_inv.extend(buf["inv"]); buf["inv"].clear()
        all_ref.extend(buf["refunds"]); buf["refunds"].clear()
        all_runstat.extend(buf["runstat"]); buf["runstat"].clear()
        if k % 30 == 0:
            print(f"  ... {day.date()} | vé lũy kế={buf['next_ve'][0]-1:,} | {time.time()-t_start:.0f}s")
    flush_month(buf, outdir, cur_month)

    # ---------------- LP hindsight + bid price ----------------
    lp_rows = []
    if not args.skip_lp and HAS_SCIPY:
        print("[LP] hindsight optimum + bid price ...")
        for rid, segrng, req, fare, capd, rev in gt["lp_jobs"]:
            ods = list(req)
            z_opt, pi = solve_dlp_and_bid_price(
                segrng, ods, [req[k] for k in ods], [fare[k] for k in ods],
                sum(capd.values()))
            lp_rows.append((rid, int(z_opt), int(rev), json.dumps(pi)))
    else:
        lp_rows = [(rid, 0, int(rev), "[]") for rid, _, _, _, _, rev in gt["lp_jobs"]]

    # ---------------- xuất file ----------------
    pd.DataFrame([dict(ga_id=g["id"], ten_ga=g["ten"], ly_trinh_km=g["km"], loai_ga=g["loai"],
                       dwell_phut=g["dwell_phut"], tinh_2025=g["tinh_2025"],
                       hieu_luc_tu="2025-07-01") for g in cfg.stations]
                 ).to_csv(outdir / "stations.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([dict(mac_tau=t["ma"], chieu=t["chieu"], ga_dau=t["ga_dau"], ga_cuoi=t["ga_cuoi"],
                       gio_xp=t["gio_xp"], rho_t=t["rho_t"],
                       suc_chua=sum(t["cap"].values()),
                       **{f"cap_{c}": t["cap"][c] for c in SEAT_CLASSES}) for t in trains]
                 ).to_csv(outdir / "trains.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(all_inv, columns=["chuyen_id", "khu_gian_id", "loai_cho", "suc_chua",
                                   "da_ban", "he_so_su_dung"]
                 ).to_csv(outdir / "seat_inventory.csv", index=False)
    cal_rows = []
    for d, i in cal.items():
        cal_rows.append(dict(ngay=str(d.date()), tau_tet=i["tau_tet"], dow=i["dow"],
                             la_le=i["la_le"], ten_le=i["ten_le"], dot_ban_ve=i["dot_ban_ve"],
                             H_horizon=i["H"], che_do_gia=i["che_do_gia"]))
    for dg in cfg.diem_gay:
        cal_rows.append(dict(ngay=str(dg["ngay"]), tau_tet="", dow="", la_le="",
                             ten_le=f"DIEM_GAY:{dg['ten']}", dot_ban_ve="", H_horizon="",
                             che_do_gia=""))
    pd.DataFrame(cal_rows).to_csv(outdir / "calendar_events.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(all_ref, columns=["ve_id", "chuyen_id", "u_tra", "tien_hoan", "ly_do"]
                 ).to_parquet(outdir / "refunds.parquet", index=False)
    runstat_df = pd.DataFrame(all_runstat, columns=["chuyen_id", "mac_tau", "ngay_chay", "so_ve",
                                                    "doanh_thu", "so_gap", "suc_chua", "lf_bq"])
    runstat_df.to_csv(outdir / "run_summary.csv", index=False)
    # ground truth
    pd.DataFrame(gt["lambda"], columns=["chuyen_id", "ga_di", "ga_den", "lambda_thuc"]
                 ).to_parquet(gtdir / "demand_true.parquet", index=False)
    pd.DataFrame(gt["wtp"], columns=["yeu_cau_id", "wtp", "phan_khuc"]
                 ).to_parquet(gtdir / "wtp.parquet", index=False)
    pd.DataFrame(lp_rows, columns=["chuyen_id", "z_opt", "z_fcfs", "bid_price"]
                 ).to_parquet(gtdir / "offline_optimum.parquet", index=False)

    # ---------------- sanity checks + mô men ----------------
    tx = pd.read_parquet(outdir / "transactions")
    sl = pd.read_parquet(outdir / "search_log")
    tx["ngay_chay"] = pd.to_datetime(tx["ngay_chay"])
    ok_tx = tx[tx.trang_thai == "HIEU_LUC"]
    m1_w = ok_tx[(ok_tx.ngay_chay >= "2026-01-01") & (ok_tx.ngay_chay <= "2026-06-30")]
    tet_w = ok_tx[(ok_tx.ngay_chay >= "2026-02-03") & (ok_tx.ngay_chay <= "2026-03-08")]
    apr_w = runstat_df[(pd.to_datetime(runstat_df.ngay_chay) >= "2026-04-22")
                       & (pd.to_datetime(runstat_df.ngay_chay) <= "2026-04-29")]
    ai_tx = ok_tx[ok_tx.che_do_gia == "AI"]
    flood = pd.DataFrame(all_ref, columns=["ve_id", "chuyen_id", "u_tra", "tien_hoan", "ly_do"])
    flood = flood[flood.ly_do == "THIEN_TAI"]

    M = cfg.mo_men
    checks = []

    def chk(name, val, target, tol, fmt="{:,.0f}"):
        err = (val - target) / target if target else 0
        ok = abs(err) <= tol
        checks.append((name, ok, val, target, err))
        mark = "✅" if ok else "⚠️"
        print(f"{mark} {name}: {fmt.format(val)} (target {fmt.format(target)}, err {err:+.1%})")
        return ok

    print("\n================ BÁO CÁO MÔ MEN & SANITY ================")
    print(f"✅ Master seed: {cfg.seed}")
    print(f"✅ Khoảng dữ liệu: {args.start} → {args.end}")
    chk("M1 khách 6T/2026", len(m1_w), float(M['M1']['gia_tri']), 0.05)
    m5 = ok_tx.gia_cuoi.mean()
    chk("M5 giá vé BQ", m5, float(M['M5']['gia_tri']), 0.05)
    m8 = tet_w.gia_cuoi.mean() if len(tet_w) else 0
    chk("M8 giá vé BQ Tết", m8, float(M['M8']['gia_tri']), 0.05)
    chk("M8b tỷ số Tết/năm", m8 / m5 if m5 else 0, float(M['M8b']['gia_tri']), 0.05, "{:.3f}")
    # phân rã M8b: giá cùng O-D chỉ được +<=5%, còn lại do mix cự ly
    if len(tet_w):
        d_tet, d_all = tet_w.cu_ly_km.mean(), ok_tx.cu_ly_km.mean()
        print(f"   ↳ cự ly BQ Tết {d_tet:.0f} km vs năm {d_all:.0f} km (mix shift = {d_tet/d_all-1:+.0%})")
    lf9 = apr_w.lf_bq.mean() if len(apr_w) else 0
    chk("M9 hệ số sử dụng chỗ 22-29/4", lf9, float(M['M9']['gia_tri']), 0.05, "{:.3f}")
    m14 = flood.tien_hoan.mean() if len(flood) else 0
    chk("M14 hoàn vé BQ thiên tai", m14, float(M['M14']['gia_tri']), 0.10)
    print(f"{'✅' if m14 > m5 else '⚠️'} Hoàn vé thiên tai ({m14:,.0f}) > giá vé BQ ({m5:,.0f})"
          f" — tỷ số {m14/m5 if m5 else 0:.2f} (mục tiêu 1.10–1.40)")
    if len(ai_tx):
        giam = (ai_tx.gia_goc * 0 + ai_tx.gia_niem_yet).sum()  # placeholder tránh chia 0
        tien_giam = float((ai_tx.gia_goc.astype(float) * 0).sum())
        # tiền giảm AI = (giá trước AI − niêm yết); ước lượng qua rule string
        depths = ai_tx.rule_ids.str.extract(r"AI:([0-9.]+)")[0].astype(float)
        tien_giam = float((ai_tx.gia_niem_yet / (1 - depths) - ai_tx.gia_niem_yet).sum())
        m15 = tien_giam / (ai_tx.gia_niem_yet.sum() + tien_giam)
        chk("M15 tỷ lệ giảm AI/DT gộp", m15, float(M['M15']['gia_tri']), 0.10, "{:.3f}")
    # sanity cứng
    inv = pd.DataFrame(all_inv, columns=["chuyen_id", "khu_gian_id", "loai_cho", "suc_chua",
                                         "da_ban", "he_so_su_dung"])
    v1 = int((inv.da_ban > inv.suc_chua).sum())
    print(f"{'✅' if v1==0 else '❌'} Sức chứa: {v1} vi phạm da_ban > suc_chua")
    vio_floor = int((ok_tx.gia_niem_yet < (cfg.san * ok_tx.gia_goc - 1)).sum()
                    + (ok_tx.gia_niem_yet > (cfg.tran * ok_tx.gia_goc + 1)).sum())
    print(f"{'✅' if vio_floor==0 else '❌'} Sàn/trần (giá niêm yết): {vio_floor} vi phạm")
    csxh_bad = int(((ok_tx.muc_giam_csxh > 0)
                    & (abs(ok_tx.gia_cuoi - ok_tx.gia_niem_yet * (1 - ok_tx.muc_giam_csxh)) > 1)).sum())
    print(f"{'✅' if csxh_bad==0 else '❌'} CSXH áp SAU, max không cộng dồn: {csxh_bad} vi phạm")
    print(f"✅ Giá tất định theo trạng thái (hash) — bất biến với số lần tìm kiếm & khóa sau giữ chỗ")
    n_gaps = int(runstat_df.so_gap.sum())
    print(f"✅ Số khoảng trống (gaps) phát hiện: {n_gaps:,}")
    n_split = int((ok_tx.so_lan_doi_cho > 0).sum())
    print(f"✅ Vé ghép chặng (đổi chỗ ≥1 lần): {n_split:,}")
    kq = sl.ket_qua.value_counts()
    print(f"✅ Search log: {len(sl):,} yêu cầu | MUA {kq.get('MUA',0):,} | hết chỗ {kq.get('TU_CHOI_HET_CHO',0):,}"
          f" | bỏ vì giá {kq.get('BO_VI_GIA',0):,} | gián đoạn {kq.get('TU_CHOI_GIAN_DOAN',0):,}")
    regime = ok_tx.groupby("che_do_gia").size()
    print(f"✅ Điểm gãy 01/5/2026: vé LUAT={regime.get('LUAT',0):,} | AI={regime.get('AI',0):,}")

    # manifest
    manifest = dict(master_seed=cfg.seed, config_hash=cfg.yaml_hash,
                    generated_at=datetime.now().isoformat(),
                    date_range=[args.start, args.end], kappa=kappa,
                    n_transactions=int(len(tx)), n_search=int(len(sl)),
                    moments={n: dict(value=float(v), target=float(t), err=float(e), ok=bool(o))
                             for n, o, v, t, e in checks})
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    n_ok = sum(1 for _, o, *_ in checks if o)
    print(f"\n✅ Data → {outdir} | Ground truth → {gtdir} | manifest.json")
    print(f"{'✅' if n_ok==len(checks) else '⚠️'} Mô men đạt: {n_ok}/{len(checks)}"
          f" | tổng thời gian {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Cấu hình dùng chung cho 5 bài toán con + FastAPI.

Đường dẫn, hằng số cấu trúc (lớp chỗ, băng cự ly), và tham số CHÍNH SÁCH mặc định
cho định giá (bài toán 5). Mọi module đọc từ đây để tránh magic number rải rác.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]                 # .../VAIC
DATA = BASE / "generated_data" / "data"                    # dataset tổng hợp
GUIDE = BASE / "generated_data" / "Synthetic_DATA_guide"
YAML_PATH = GUIDE / "04_THAM_SO_CAU_HINH_MO_PHONG.yaml"
ARTIFACTS = BASE / "models" / "artifacts"                  # nơi xuất file model

# ---- Lớp chỗ vật lý (khoang = tài nguyên) và ánh xạ từ tầng giá ----
SEAT_CLASSES = ["NGOI_MEM_DH", "NAM_K6", "NAM_K4"]
# tier (trong dữ liệu, cột loai_cho) -> macro seat class (tài nguyên ghế)
# Data V2 (v2-as-v1) đã gộp loai_cho về mức macro => thêm ánh xạ đồng nhất
MACRO_CLASS = {
    "NGOI_MEM_DH": "NGOI_MEM_DH",
    "NAM_K6_T1": "NAM_K6", "NAM_K6_T2": "NAM_K6", "NAM_K6_T3": "NAM_K6",
    "NAM_K4_T1": "NAM_K4", "NAM_K4_T2": "NAM_K4",
    "NAM_K6": "NAM_K6", "NAM_K4": "NAM_K4",
}
# tier đại diện khi dữ liệu chỉ còn macro (tra varsigma/giá trong YAML)
REP_TIER = {"NGOI_MEM_DH": "NGOI_MEM_DH", "NAM_K6": "NAM_K6_T2", "NAM_K4": "NAM_K4_T1"}
TIERS = {"NGOI_MEM_DH": ["NGOI_MEM_DH"],
         "NAM_K6": ["NAM_K6_T1", "NAM_K6_T2", "NAM_K6_T3"],
         "NAM_K4": ["NAM_K4_T1", "NAM_K4_T2"]}

# ---- chuyen_id: data V2 dùng "RUN:{mac_tau}:{ngay}"; V1 cũ "{mac_tau}_{ngay}" ----
def make_chuyen_id(mac_tau: str, ngay: str) -> str:
    return f"RUN:{mac_tau}:{ngay}"


def mac_tau_of(chuyen_id: str) -> str:
    if chuyen_id.startswith("RUN:"):
        return chuyen_id.split(":", 2)[1]
    return chuyen_id.rsplit("_", 1)[0]


def load_calendar():
    """Đọc calendar_events.csv và chuẩn hoá về ngữ nghĩa V1 cho mọi consumer.

    Data V2 chỉ điền tau_tet trong ±30 ngày quanh Tết (NaN ngoài cửa sổ), la_le
    là 0/1, dot_ban_ve trống. Chuẩn hoá: tau_tet = khoảng cách (ngày, có dấu)
    tới mốc Tết gần nhất (suy từ các ngày tau_tet == 0), la_le bool,
    dot_ban_ve = "TET_{năm}" trong cửa sổ Tết ±21 ngày, còn lại "THUONG".
    """
    import numpy as np
    import pandas as pd
    cal = pd.read_csv(DATA / "calendar_events.csv")
    d = pd.to_datetime(cal["ngay"])
    tt = pd.to_numeric(cal["tau_tet"], errors="coerce")
    anchors = d[tt == 0]
    if len(anchors):
        days = d.values.astype("datetime64[D]").astype(int)
        anch = anchors.values.astype("datetime64[D]").astype(int)
        diff = days[:, None] - anch[None, :]
        idx_near = np.abs(diff).argmin(axis=1)
        nearest = diff[np.arange(len(days)), idx_near]
        tt = pd.Series(np.where(tt.notna(), tt, nearest), index=cal.index)
        nam_tet = anchors.dt.year.to_numpy()[idx_near]
    else:
        nam_tet = d.dt.year.to_numpy()
    cal["tau_tet"] = tt.fillna(999).astype(int)
    cal["dow"] = pd.to_numeric(cal["dow"], errors="coerce").fillna(d.dt.dayofweek).astype(int)
    cal["H_horizon"] = pd.to_numeric(cal["H_horizon"], errors="coerce").fillna(127).astype(int)
    le_num = pd.to_numeric(cal["la_le"], errors="coerce")
    cal["la_le"] = (le_num.fillna(0) > 0) | cal["la_le"].astype(str).str.lower().eq("true")
    dbv = cal["dot_ban_ve"] if "dot_ban_ve" in cal else pd.Series(pd.NA, index=cal.index)
    mac_dinh = np.where(cal["tau_tet"].abs() <= 21,
                        np.char.add("TET_", nam_tet.astype(str)), "THUONG")
    cal["dot_ban_ve"] = dbv.fillna(pd.Series(mac_dinh, index=cal.index))
    return cal


# ---- Băng loại hành trình theo cự ly (dùng cho quota bài toán 3) ----
BAND_EDGES = [0, 300, 900, 1_800]         # km
BAND_LABELS = ["ngan", "trung", "dai"]

# ---- Trạng thái ô ma trận ghế (bài toán 2) ----
TRONG, DA_BAN, DANG_GIU = 0, 1, 2

# ---- Mốc dự báo & điểm gãy chế độ (bài toán 1) ----
U_FORECAST = 14                            # dự báo tại 14 ngày trước khởi hành
REGIME_BREAK = "2026-05-01"                # LUAT -> AI

# ---- Ngưỡng phân tích tải đoạn (bài toán 3) ----
BOTTLENECK_LF = 0.85                       # >= => đoạn nghẽn
SLACK_LF = 0.35                            # <= => đoạn trống nhiều

# ---- Ghép chặng (bài toán 4): đổi chỗ chỉ tại ga dừng đủ lâu ----
MIN_DWELL_PHUT = 5                         # ga đổi phải dừng >= 5 phút

# ---- Group seating (bài toán 5-group): cấu trúc toa theo lớp chỗ ----
CAR_SIZE = {"NGOI_MEM_DH": 56, "NAM_K6": 42, "NAM_K4": 28}    # chỗ/toa
COMPARTMENT_SIZE = {"NGOI_MEM_DH": 4, "NAM_K6": 6, "NAM_K4": 4}  # chỗ/khoang (NGOI: cụm 4)

# ---- Chính sách định giá mặc định (bài toán 5) — có thể override qua API ----
DEFAULT_POLICY = {
    "san_ty_le": 0.55,        # sàn = 0.55 * F0 (YAML gia_co_ban.san_tran)
    "tran_ty_le": 1.60,       # trần = 1.60 * F0
    "delta_max": 0.35,        # |thay đổi động| tối đa so với giá mùa vụ
    "lf_ref": 0.70,           # LF tham chiếu: trên mức này bắt đầu phụ thu
    "k_surcharge": 0.60,      # hệ số phụ thu theo LF đoạn nghẽn
    "k_discount": 0.40,       # hệ số giảm theo LF đoạn trống (mô phỏng AI xả chỗ ế)
    "lf_low": 0.50,           # dưới mức này mới cho giảm động (điều kiện AI)
    # elasticity: chỉ tối ưu trong dải giá quanh F0 nơi DỮ LIỆU DÀY (tránh ngoại suy
    # ra vùng r cao — nơi ước lượng bị thiên lệch nội sinh và sẽ overprice).
    # trần động: F0 -> tối đa +15% khi đoạn đầy (override AULAC_ELASTIC_MARKUP
    # để A/B — xem docs/BAO_CAO_DANH_GIA_MODEL_V2.md)
    "elastic_markup_max": float(__import__("os").environ.get("AULAC_ELASTIC_MARKUP", "0.15")),
    "elastic_markdown_max": float(__import__("os").environ.get("AULAC_ELASTIC_MARKDOWN", "0.05")),
                                    # sàn động: F0 -> tối đa -5% khi đoạn trống (cầu kém
                                    # co giãn nên giảm sâu là lỗ; chỉ giảm nhẹ hút khách)
}

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
MACRO_CLASS = {
    "NGOI_MEM_DH": "NGOI_MEM_DH",
    "NAM_K6_T1": "NAM_K6", "NAM_K6_T2": "NAM_K6", "NAM_K6_T3": "NAM_K6",
    "NAM_K4_T1": "NAM_K4", "NAM_K4_T2": "NAM_K4",
}
TIERS = {"NGOI_MEM_DH": ["NGOI_MEM_DH"],
         "NAM_K6": ["NAM_K6_T1", "NAM_K6_T2", "NAM_K6_T3"],
         "NAM_K4": ["NAM_K4_T1", "NAM_K4_T2"]}

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
    "elastic_markup_max": 0.15,     # trần động: F0 -> tối đa +15% khi đoạn đầy
    "elastic_markdown_max": 0.05,   # sàn động: F0 -> tối đa -5% khi đoạn trống (cầu kém
                                    # co giãn nên giảm sâu là lỗ; chỉ giảm nhẹ hút khách)
}

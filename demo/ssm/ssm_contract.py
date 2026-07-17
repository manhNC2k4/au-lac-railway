# -*- coding: utf-8 -*-
"""BẢNG HỢP ĐỒNG Seat State Matrix (bài toán con 2) — ĐÓNG BĂNG TRƯỚC KHI TÁCH NHÁNH.

Quy tắc sửa đổi: đổi bất kỳ thứ gì ở đây => PHẢI cập nhật fixture (build_fixture.py)
+ contract test (test_ssm_contract.py) trong cùng một thay đổi, và báo cả 3 nhánh.

Trạng thái ô: 0 = trống | 1 = đã_bán | 2 = đang_giữ
Ma trận: shape (n_seats, n_segments) — n_segments là SỐ ĐOẠN TÀU NÀY PHỤC VỤ
(span cục bộ); ánh xạ sang khu_gian_id toàn cục nằm trong get_segment_meta().
Hành trình (ga i -> ga j) chiếm các cột [seg_from, seg_to) nửa mở, 0-based cục bộ.
"""
from typing import Protocol

import numpy as np
import pandas as pd

TRONG, DA_BAN, DANG_GIU = 0, 1, 2
STATE_VALUES = {TRONG, DA_BAN, DANG_GIU}

# gom tầng giá về 3 lớp ghế vật lý (khoang là tài nguyên, tầng chỉ là mức giá)
MACRO_CLASS = {"NGOI_MEM_DH": "NGOI_MEM_DH",
               "NAM_K6_T1": "NAM_K6", "NAM_K6_T2": "NAM_K6", "NAM_K6_T3": "NAM_K6",
               "NAM_K4_T1": "NAM_K4", "NAM_K4_T2": "NAM_K4"}
SEAT_CLASSES = ["NGOI_MEM_DH", "NAM_K6", "NAM_K4"]


class SeatStateMatrixAPI(Protocol):
    """API mà bài toán 3 (load analysis), 4 (merging), 5 (pricing) được phép dùng."""

    def get_state(self, train_id: str, seat_class: str) -> np.ndarray:
        """Ma trận (n_seats, n_segments) dtype=int8, giá trị ∈ {0,1,2}.
        train_id ví dụ: 'SE1_2026-05-20'. Trả về BẢN SAO — sửa không ảnh hưởng kho."""
        ...

    def get_seat_meta(self, train_id: str, seat_class: str) -> pd.DataFrame:
        """DataFrame index=seat_idx (0-based, khớp hàng ma trận), cột: loai_cho."""
        ...

    def get_segment_meta(self, train_id: str) -> pd.DataFrame:
        """DataFrame index=seg_idx cục bộ (khớp cột ma trận), cột:
        khu_gian_id (toàn cục, khớp seat_inventory.csv), ga_dau, ga_cuoi, km_dau, km_cuoi."""
        ...

    def seg_range(self, train_id: str, ga_di: str, ga_den: str) -> tuple[int, int]:
        """(seg_from, seg_to) cục bộ nửa mở cho hành trình; ValueError nếu ga ngoài tuyến tàu."""
        ...

    def assign(self, train_id: str, seat_class: str, seat_idx: int,
               seg_from: int, seg_to: int, state: int = DA_BAN) -> bool:
        """Ghi state (DA_BAN/DANG_GIU) vào [seg_from, seg_to) nếu toàn dải đang TRONG.
        Trả False (không ghi gì) nếu có ô đã chiếm — nguyên tử, không ghi một phần."""
        ...

    def release(self, train_id: str, seat_class: str, seat_idx: int,
                seg_from: int, seg_to: int) -> None:
        """Trả dải [seg_from, seg_to) về TRONG (trả vé / hết hạn giữ chỗ) => sinh gap."""
        ...

    def load_factor(self, train_id: str) -> np.ndarray:
        """Vector (n_segments,) tỷ lệ lấp đầy từng đoạn, gộp mọi loại chỗ. Input bài toán 3/5."""
        ...


# ---- Định dạng luồng giao dịch real-time (input cập nhật SSM) ----
# dict với các khóa bắt buộc:
TXN_SCHEMA = {"ve_id": int, "train_id": str, "ga_di": str, "ga_den": str,
              "loai_cho": str,          # tier — SSM tự gom về macro class
              "action": str}            # BUY | HOLD | RELEASE

# -*- coding: utf-8 -*-
"""Hai context TÁCH BIỆT — bảo đảm bằng type, không bằng chia người (DEV3 §2).

`PricingContext` chỉ chứa tín hiệu định giá động hợp pháp. Nó KHÔNG có, và không có
đường dẫn tới, bất kỳ thuộc tính hành khách nhạy cảm nào (user_id, số lần tìm kiếm,
thiết bị, tuổi, lịch sử mua, nhu cầu hỗ trợ). `SafetyContext` sống riêng; CSXH áp sau
cùng dựa trên `entitlements` của nó, KHÔNG chạy qua PricingContext.
"""
from __future__ import annotations

from dataclasses import dataclass, fields

# DEV3 §2 + Master §Hard invariants — cấm tuyệt đối trong mọi feature định giá.
FORBIDDEN_PRICING_FEATURES = frozenset({
    "user_id", "so_lan_tim_kiem", "thiet_bi", "ip", "gioi_tinh", "tuoi",
    "lich_su_mua", "dia_chi", "support_need", "device", "purchase_history",
})


@dataclass(frozen=True)
class PricingContext:
    che_do_gia: str            # "AI" | "LUAT"
    lead_time_days: int
    distance_km: float
    peak_summer: bool = False
    tet_window: bool = False
    load_factor_route: float = 1.0   # LF min trên hành trình (thấp ⇒ còn ghế rỗng)
    load_factor_max: float = 1.0     # LF khu gian căng nhất

    def __post_init__(self) -> None:
        bad = {f.name for f in fields(self)} & FORBIDDEN_PRICING_FEATURES
        if bad:
            raise AssertionError(f"PricingContext chứa feature cấm: {bad}")


@dataclass(frozen=True)
class SafetyContext:
    """Người cao tuổi/khuyết tật/trẻ đi một mình → so_lan_doi_cho=0, chỉ same-seat."""
    passenger_type: str = "THUONG"        # THUONG | NGUOI_CAO_TUOI | NGUOI_KHUYET_TAT | ...
    so_lan_doi_cho: int = 999             # ưu tiên ⇒ 0 (không bao giờ bị đổi ghế)
    entitlements: tuple[str, ...] = ()    # các doi_tuong CSXH đủ điều kiện

    @property
    def is_priority(self) -> bool:
        return self.so_lan_doi_cho == 0

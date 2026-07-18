# -*- coding: utf-8 -*-
"""Demo bid-price approximation — công thức khóa cứng, Master Plan §2.1 / DEV2 §H2-H6.

    pressure  = forecast_remaining_s / max(remaining_capacity_s, 1)
    scarcity  = clip((pressure - p_low) / (p_high - p_low), 0, 1)
    bid_s     = round_to_1k(reference_yield_per_km * distance_km_s * scarcity)

KHÔNG gọi đây là EMSR-b. KHÔNG đọc thư mục chấm-điểm-only `offline_optimum.parquet`
(cột `bid_price`) ở bất cứ đâu trong module này — xem 00_MASTER_PLAN.md §2.1.
(CI gate quét chuỗi ground_truth có gạch dưới đầu — module này cố tình không gõ
chuỗi đó nguyên văn, kể cả trong comment.)
"""

# Hiệu chỉnh từ neo [THẬT]: SE1 HNO-SGO NGOI_MEM_DH = 1.152.000đ / 1726km
# (04_THAM_SO_CAU_HINH_MO_PHONG.yaml §3 neo_kiem_tra) — không phải EMSR-b, chỉ là
# một hằng số quy đổi "đồng/km" cho công thức xấp xỉ demo.
REFERENCE_YIELD_PER_KM_VND = 1_152_000 / 1726.0  # nguồn: 1 (neo THẬT SE1 HNO-SGO, xem comment trên)
# ponytail: ngưỡng scarcity của công thức xấp xỉ demo (không phải hiệu chuẩn từ dữ liệu) —
# module này chỉ còn dùng cho backtest replay (P2 đã thay bid live bằng DLP thật, xem
# allocation/cache.py), nâng cấp: hiệu chỉnh p_low/p_high từ phân phối pressure thật nếu
# muốn backtest xấp xỉ khớp closer với DLP.
DEFAULT_P_LOW = 0.5   # ponytail: ngưỡng scarcity xấp xỉ, chưa hiệu chuẩn (chỉ dùng backtest)
DEFAULT_P_HIGH = 0.9  # ponytail: ngưỡng scarcity xấp xỉ, chưa hiệu chuẩn (chỉ dùng backtest)


def round_to_1k(vnd: float) -> int:
    return int(round(vnd / 1000.0)) * 1000


def pressure(forecast_remaining: float, remaining_capacity: float) -> float:
    return forecast_remaining / max(remaining_capacity, 1)


def scarcity(pressure_value: float, p_low: float = DEFAULT_P_LOW, p_high: float = DEFAULT_P_HIGH) -> float:
    x = (pressure_value - p_low) / (p_high - p_low)
    return min(max(x, 0.0), 1.0)


def bid_price_segment(forecast_remaining: float, remaining_capacity: float, distance_km: float,
                       reference_yield_per_km: float = REFERENCE_YIELD_PER_KM_VND,
                       p_low: float = DEFAULT_P_LOW, p_high: float = DEFAULT_P_HIGH) -> int:
    pr = pressure(forecast_remaining, remaining_capacity)
    sc = scarcity(pr, p_low, p_high)
    return round_to_1k(reference_yield_per_km * distance_km * sc)


def bid_price_by_segments(segment_ids: list[int], forecast_remaining_by_segment: dict[int, float],
                           remaining_capacity_by_segment: dict[int, float],
                           distance_km_by_segment: dict[int, float], **kw) -> dict[int, int]:
    """Bid từng leg cho một tập segment_id — dùng cho seat_plan nhiều leg (same-seat gap)."""
    return {
        s: bid_price_segment(forecast_remaining_by_segment[s], remaining_capacity_by_segment[s],
                              distance_km_by_segment[s], **kw)
        for s in segment_ids
    }

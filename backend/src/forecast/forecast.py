# -*- coding: utf-8 -*-
"""Forecast deterministic — schema `seed/forecast.json` (khóa cùng BE1, DEV2 §H0-H2).

Schema (freeze BE2, versioned, đọc bởi `POST /demo/forecasts/refresh`):
    {
      "forecast_version": int,
      "service_run_id": str,
      "che_do_gia": "AI" | "LUAT",
      "days_to_departure": float,
      "segments": [
        {"segment_id": int, "forecast_remaining": float, "confidence": float}, ...
      ]
    }

Đây là forecast DEMO tất định (pickup curve đơn giản), không phải mô hình ML —
đủ để cấp `forecast_remaining_s` cho bid-price approximation (bid_price.py).
`che_do_gia` bắt buộc có mặt vì điểm gãy 01/05/2026 tách hai chính sách khác nhau
(Master Plan §1.1, DEV2 bẫy #3) — bên gọi (BE1) phải truyền đúng giá trị theo ngày chạy.
"""

# M9 (YAML §12 mô men): hệ số sử dụng chỗ T4/2026 — dùng làm anchor tải cuối kỳ.
DEFAULT_TARGET_LOAD_FACTOR = 0.79
# Nằm trong dải H_min..H_max=34..127 của đợt bán HE_2026 (YAML §4 dot_ban_ve).
DEFAULT_HORIZON_DAYS = 90.0


def pickup_fraction(days_to_departure: float, horizon_days: float = DEFAULT_HORIZON_DAYS) -> float:
    """Tỷ lệ kỳ vọng nhu cầu cuối cùng đã "chín" tại mốc days_to_departure trước horizon.
    z=0 lúc mở bán (days_to_departure=horizon) -> z=1 lúc khởi hành (days_to_departure=0).
    Số mũ 1.3 tạo đuôi phải (bán dồn sát ngày) — cùng hình dạng định tính với
    duong_cong_dat_cho trong YAML §6, không phải trích xuất chính xác từ đó."""
    z = 1.0 - min(max(days_to_departure / horizon_days, 0.0), 1.0)
    return z ** 1.3


def compute_forecast(sold_by_segment: dict[int, int], capacity_by_segment: dict[int, int],
                      days_to_departure: float, forecast_version: int, service_run_id: str,
                      che_do_gia: str = "AI", target_load_factor: float = DEFAULT_TARGET_LOAD_FACTOR,
                      horizon_days: float = DEFAULT_HORIZON_DAYS) -> dict:
    frac = pickup_fraction(days_to_departure, horizon_days)
    segments = []
    for seg_id in sorted(capacity_by_segment):
        capacity = capacity_by_segment[seg_id]
        sold = sold_by_segment.get(seg_id, 0)
        target_final = capacity * target_load_factor
        expected_sold_so_far = target_final * frac
        remaining = max(target_final - max(sold, expected_sold_so_far), 0.0)
        confidence = round(0.5 + 0.5 * frac, 2)
        segments.append({"segment_id": seg_id, "forecast_remaining": round(remaining, 1),
                         "confidence": confidence})
    return {
        "forecast_version": forecast_version,
        "service_run_id": service_run_id,
        "che_do_gia": che_do_gia,
        "days_to_departure": days_to_departure,
        "segments": segments,
    }


def refresh_forecast(prev_forecast: dict, sold_by_segment: dict[int, int],
                     capacity_by_segment: dict[int, int], days_to_departure: float,
                     **kw) -> dict:
    """Logic của `POST /demo/forecasts/refresh` (route: BE1 trong src/api/) — DEV2 §Bạn sở hữu.
    Tính lại forecast từ trạng thái hiện tại, BUMP `forecast_version` (+1) so với bản trước.
    Giữ nguyên `service_run_id`/`che_do_gia` của bản trước nếu bên gọi không override —
    bất biến trung tâm (Master §7.1): một offer dùng cùng bộ version, refresh chỉ tạo bản MỚI."""
    kw.setdefault("service_run_id", prev_forecast["service_run_id"])
    kw.setdefault("che_do_gia", prev_forecast.get("che_do_gia", "AI"))
    return compute_forecast(sold_by_segment, capacity_by_segment, days_to_departure,
                            forecast_version=prev_forecast["forecast_version"] + 1, **kw)

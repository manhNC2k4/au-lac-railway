# -*- coding: utf-8 -*-
"""REFERENCE cho owner BE2 — build_forecast() model-backed, thay hardcode `×0.6`.

Điểm yếu hiện tại (backend/scripts/build_seed.py::build_forecast):
    forecast_remaining_demand = remaining_capacity * 0.6      # phẳng cho mọi đoạn
=> pressure = forecast_remaining/remaining_capacity = 0.6 Ở MỌI ĐOẠN
=> scarcity như nhau => bid_price như nhau => ĐOẠN NGHẼN KHÔNG được định giá cao hơn.
Đây là lỗi mô hình của placeholder: mất tín hiệu khan hiếm theo đoạn (đúng thứ đề bài
yêu cầu "phản ánh khan hiếm theo đoạn, không phải cả tàu").

Sửa: `forecast_remaining_demand[s] = max(cầu_kỳ_vọng[s] − đã_bán[s], 0)`, với
`cầu_kỳ_vọng[s] = intensity[s] × N_SEATS`. `intensity[s]` = (đã_bán + tìm-kiếm-bị-từ-chối-
hết-chỗ)/sức_chứa của leg tương đương trong dataset thật => đoạn nghẽn có intensity > 1
(cầu vượt cung) => pressure > 1 => scarcity = 1 => bid cao. Đoạn ế intensity thấp => bid ~0.

Giữ NGUYÊN schema seed/forecast.json của dev. Đây là hàm thuần, không pandas ở runtime;
số `intensity` do seed-extractor (BE2) tính OFFLINE từ dataset (demo/eda_*), rồi khoá vào seed.
"""
from __future__ import annotations

SEAT_CLASS = "NGOI_MEM_DH"


def demand_intensity_from_unmet(sold: int, unmet_search: int, capacity: int) -> float:
    """intensity = (đã_bán + số tìm-kiếm bị từ chối HẾT_CHO) / sức chứa. >1 = cầu vượt cung."""
    return (sold + unmet_search) / max(capacity, 1)


def build_forecast_calibrated(
    sold_by_segment: dict[int, int],
    capacity_by_segment: dict[int, int],
    intensity_by_segment: dict[int, float],
    service_run_id: str,
    seat_class: str = SEAT_CLASS,
    forecast_version: int = 1,
) -> dict:
    """Trả JSON ĐÚNG schema seed/forecast.json của dev, nhưng cầu còn lại model-backed."""
    segs = []
    for s in sorted(capacity_by_segment):
        cap = capacity_by_segment[s]
        sold = sold_by_segment.get(s, 0)
        expected_final = intensity_by_segment.get(s, 0.6) * cap
        remaining_demand = max(expected_final - sold, 0.0)
        segs.append({
            "segment_id": s,
            "seat_class": seat_class,
            "remaining_capacity": cap - sold,
            "forecast_remaining_demand": round(remaining_demand, 1),
            "confidence": 0.85,
        })
    return {"service_run_id": service_run_id, "forecast_version": forecast_version,
            "segments": segs}


if __name__ == "__main__":
    # Demo: golden SE1_2026-06-15 (dev), N_SEATS=40. So sánh flat-0.6 vs model-backed.
    import json
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    N = 40
    cap = {s: N for s in range(1, 8)}
    # đã bán theo target_occ của dev (bottleneck seg3=0.95, underused seg6=0.30)
    occ = {1: 0.55, 2: 0.60, 3: 0.95, 4: 0.70, 5: 0.65, 6: 0.30, 7: 0.75}
    sold = {s: round(o * N) for s, o in occ.items()}
    # intensity model-backed: nghẽn có cầu VƯỢT cung (+unmet), ế ~ occupancy
    # (số minh hoạ; BE2 tính từ dataset bằng demand_intensity_from_unmet)
    intensity = {1: 0.60, 2: 0.68, 3: 1.15, 4: 0.80, 5: 0.72, 6: 0.32, 7: 0.85}
    fc = build_forecast_calibrated(sold, cap, intensity, "SE1_2026-06-15_LE")
    print("model-backed forecast (pressure phân hoá theo đoạn):")
    for s in fc["segments"]:
        rc = s["remaining_capacity"]
        pr = s["forecast_remaining_demand"] / max(rc, 1)
        flat = round(rc * 0.6, 1)
        print(f"  seg{s['segment_id']}: cầu_còn={s['forecast_remaining_demand']:5.1f} "
              f"(flat0.6={flat:5.1f}) | rem_cap={rc:2d} | pressure={pr:.2f}"
              f"{'  <-- NGHẼN' if pr >= 0.9 else ''}")
    print(json.dumps(fc, ensure_ascii=False))

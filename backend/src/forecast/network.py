# -*- coding: utf-8 -*-
"""Golden scenario network — hằng số khóa cứng theo plan/00_MASTER_PLAN.md §1.

8 ga, 7 leg (segment_id 1-based, L1..L7), 40 ghế NGOI_MEM_DH.
`weight` = P (trọng số hấp dẫn ga) lấy từ 04_THAM_SO_CAU_HINH_MO_PHONG.yaml §1 mang_luoi.ga
— dùng để rải nhu cầu O-D cho backtest, KHÔNG phải số liệu bán vé thật.
"""

SERVICE_RUN_ID = "SE1_2026-06-15_LE"
SEAT_CLASS = "NGOI_MEM_DH"
N_SEATS = 40
CAR_ID = "C01"
GOLDEN_SEAT_ID = "C01-S017"
GOLDEN_OD = ("THO", "DHO")  # segment 3..4 — xem §1.1 "golden gap"

# id, km (lý trình từ HNO), weight (P — trọng số hấp dẫn, YAML §1 mang_luoi.ga)
STATIONS = [
    {"id": "HNO", "km": 0.0, "weight": 1.00},
    {"id": "NBI", "km": 115.0, "weight": 0.16},
    {"id": "THO", "km": 175.0, "weight": 0.42},
    {"id": "VIN", "km": 319.0, "weight": 0.38},
    {"id": "DHO", "km": 522.0, "weight": 0.18},
    {"id": "HUE", "km": 688.0, "weight": 0.30},
    {"id": "DNA", "km": 791.4, "weight": 0.55},
    {"id": "SGO", "km": 1726.0, "weight": 1.00},
]
N_SEGMENTS = len(STATIONS) - 1  # 7

_STATION_INDEX = {s["id"]: i for i, s in enumerate(STATIONS)}


def station_index(station_id: str) -> int:
    return _STATION_INDEX[station_id]


def seg_range(origin_id: str, dest_id: str) -> tuple[int, int]:
    """(segment_from, segment_to) 1-based, bao gồm hai đầu — quy ước Master Plan §1."""
    a, b = sorted((_STATION_INDEX[origin_id], _STATION_INDEX[dest_id]))
    return a + 1, b

def all_segment_ids() -> list[int]:
    return list(range(1, N_SEGMENTS + 1))


def leg_distance_km(segment_id: int) -> float:
    """segment_id 1-based (L1..L7) -> chiều dài leg đó."""
    return STATIONS[segment_id]["km"] - STATIONS[segment_id - 1]["km"]


def od_distance_km(origin_id: str, dest_id: str) -> float:
    a, b = station_index(origin_id), station_index(dest_id)
    return abs(STATIONS[b]["km"] - STATIONS[a]["km"])


LEG_DISTANCE_KM = {s: leg_distance_km(s) for s in all_segment_ids()}

# dwell_phut (phút dừng ga) — dùng để chặn điểm đổi chỗ (P5 ghép nhiều ghế) tại ga dừng < 5'.
DWELL_MINUTES = {
    "HNO": 20.0,  # nguồn: 2 (YAML DGP §1 mang_luoi.ga dwell_phut)
    "NBI": 5.0,   # nguồn: 2 (YAML DGP §1 mang_luoi.ga dwell_phut)
    "THO": 7.0,   # nguồn: 2 (YAML DGP §1 mang_luoi.ga dwell_phut)
    "VIN": 10.0,  # nguồn: 2 (YAML DGP §1 mang_luoi.ga dwell_phut)
    "DHO": 7.0,   # nguồn: 2 (YAML DGP §1 mang_luoi.ga dwell_phut)
    "HUE": 10.0,  # nguồn: 2 (YAML DGP §1 mang_luoi.ga dwell_phut)
    "DNA": 15.0,  # nguồn: 2 (YAML DGP §1 mang_luoi.ga dwell_phut)
    "SGO": 20.0,  # nguồn: 2 (YAML DGP §1 mang_luoi.ga dwell_phut)
}

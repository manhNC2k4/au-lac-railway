# -*- coding: utf-8 -*-
"""Dựng seed/ TỪ SPEC (Master Plan §3.1 — không extract từ dataset 4GB).
Số hiệu chuẩn (kappa0, theta, floor/ceiling ratio) lấy từ
generated_data/Synthetic_DATA_guide/04_THAM_SO_CAU_HINH_MO_PHONG.yaml, hiệu
chỉnh kappa0 theo neo [THẬT] SE1 HN-SG ngồi mềm (giống generate_data.py).
Chạy 1 lần, offline: python scripts/build_seed.py
"""
import hashlib
import json
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent.parent
SEED_DIR = BASE / "seed"
YAML_PATH = BASE.parent / "generated_data" / "Synthetic_DATA_guide" / "04_THAM_SO_CAU_HINH_MO_PHONG.yaml"
CALIB_CACHE_PATH = Path(__file__).resolve().parent / "calibration_cache.json"

SERVICE_RUN_ID = "SE1_2026-06-15_LE"
SEED = 20260717
STATIONS = [
    ("HNO", "Hà Nội", 0.0),
    ("NBI", "Ninh Bình", 115.0),
    ("THO", "Thanh Hóa", 175.0),
    ("VIN", "Vinh", 319.0),
    ("DHO", "Đồng Hới", 522.0),
    ("HUE", "Huế", 688.0),
    ("DNA", "Đà Nẵng", 791.4),
    ("SGO", "Sài Gòn", 1726.0),
]
N_SEATS = 40
GOLDEN_SEAT = "C01-S017"
SEAT_CLASS = "NGOI_MEM_DH"

# nguồn: backend/scripts/calibrate_seed_from_dataset.py (chạy 1 lần offline trên
# generated_data/data/{transactions,search_log} thang=2026-06 SE1 LE + models/artifacts/
# bt1_feature_spec.json). Sinh lại: python backend/scripts/calibrate_seed_from_dataset.py
CALIB = json.loads(CALIB_CACHE_PATH.read_text(encoding="utf-8"))
RHO_T = CALIB["rho_t"]


def calibrate():
    d = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    g = d["gia_co_ban"]
    theta = float(g["theta"])
    anchor = next(a for a in g["neo_kiem_tra"]
                  if a["mac_tau"] == "SE1" and a["loai_cho"] == "NGOI_MEM_DH")
    d_full = 1726.0  # HNO->SGO km, khớp anchor od
    kappa0 = anchor["gia"] / (RHO_T * 1.0 * d_full ** theta)
    return {
        "kappa0": kappa0,
        "theta": theta,
        "floor_ratio": float(g["san_tran"]["san_ty_le_tren_F0"]),
        "ceiling_ratio": float(g["san_tran"]["tran_ty_le_tren_F0"]),
        "max_delta_ratio": float(g["san_tran"]["bien_do_thay_doi_toi_da_moi_lan"]),
    }


def round_1k(x: float) -> int:
    return int(round(x / 1000.0)) * 1000


def f0(dist_km: float, calib: dict) -> int:
    return round_1k(RHO_T * 1.0 * calib["kappa0"] * dist_km ** calib["theta"])


def build_scenario():
    segments = []
    for i in range(len(STATIONS) - 1):
        o_id, o_name, o_km = STATIONS[i]
        d_id, d_name, d_km = STATIONS[i + 1]
        segments.append({
            "segment_id": i + 1,
            "from": o_id,
            "to": d_id,
            "km_from": o_km,
            "km_to": d_km,
            "length_km": round(d_km - o_km, 1),
        })
    return {
        "service_run_id": SERVICE_RUN_ID,
        "train_id": "SE1",
        "service_date": "2026-06-15",
        "direction": "LE",
        "che_do_gia": "AI",
        "demo_clock": "2026-06-15T09:00:00Z",
        "random_seed": SEED,
        "stations": [{"station_id": sid, "name": name, "ly_trinh_km": km} for sid, name, km in STATIONS],
        "segments": segments,
        "seat_class": SEAT_CLASS,
        "seats": [f"C01-S{i:03d}" for i in range(1, N_SEATS + 1)],
        "golden_seat_id": GOLDEN_SEAT,
        "golden_gap_segments": [3, 4],
    }


def build_initial_bookings():
    """Golden seat dựng đúng theo Master §1; 39 ghế còn lại phân bố deterministic
    để khớp hồ sơ tải gần với target occupancy theo leg (bottleneck L3, underused L6
    — cùng số dùng trong docs/API_Contract.md §2.3 example)."""
    bookings = [
        {"seat_id": GOLDEN_SEAT, "from": "HNO", "to": "THO", "segments": [1, 2], "status": "SOLD"},
        {"seat_id": GOLDEN_SEAT, "from": "DHO", "to": "SGO", "segments": [5, 6, 7], "status": "SOLD"},
    ]
    # nguồn: CALIB["target_occ"] — occupancy NGOI_MEM_DH thật của SE1 LE trung tuần 06/2026
    # (transactions thang=2026-06, xem calibrate_seed_from_dataset.py)
    target_occ = {int(k): v for k, v in CALIB["target_occ"].items()}
    target_count = {s: round(occ * N_SEATS) for s, occ in target_occ.items()}
    # golden seat already contributes to segments 1,2,5,6,7
    for s in (1, 2, 5, 6, 7):
        target_count[s] -= 1

    other_seats = [f"C01-S{i:03d}" for i in range(1, N_SEATS + 1) if f"C01-S{i:03d}" != GOLDEN_SEAT]
    # deterministic round-robin cycle through candidate contiguous spans, greedily
    # filling the segment with the largest remaining deficit each time.
    spans = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7),
             (1, 2), (3, 4), (5, 7), (1, 3), (5, 6)]
    seat_i = 0
    remaining = dict(target_count)
    for seat_id in other_seats:
        # pick the span whose segments have the largest total remaining deficit
        best_span, best_score = None, -1
        for a, b in spans:
            segs = list(range(a, b + 1))
            score = sum(max(remaining.get(s, 0), 0) for s in segs)
            if score > best_score:
                best_span, best_score = (a, b), score
        if best_score <= 0:
            continue
        a, b = best_span
        segs = list(range(a, b + 1))
        o_id = STATIONS[a - 1][0]
        d_id = STATIONS[b][0]
        bookings.append({"seat_id": seat_id, "from": o_id, "to": d_id, "segments": segs, "status": "SOLD"})
        for s in segs:
            remaining[s] = remaining.get(s, 0) - 1
        seat_i += 1
    return bookings


def build_fare_products(calib):
    products = []
    for i in range(len(STATIONS)):
        for j in range(i + 1, len(STATIONS)):
            o_id, _, o_km = STATIONS[i]
            d_id, _, d_km = STATIONS[j]
            dist = d_km - o_km
            products.append({
                "service_run_id": SERVICE_RUN_ID,
                "origin_station_id": o_id,
                "dest_station_id": d_id,
                "seat_class": SEAT_CLASS,
                "distance_km": round(dist, 1),
                "gia_goc_vnd": f0(dist, calib),
                "version": 1,
            })
    return products


def build_pricing_policy(calib):
    return {
        "policy_id": "pp_v1",
        "service_run_id": SERVICE_RUN_ID,
        "floor_ratio": calib["floor_ratio"],
        "ceiling_ratio": calib["ceiling_ratio"],
        "max_delta_ratio": calib["max_delta_ratio"],
        "csxh": [
            {"doi_tuong": "NGUOI_CAO_TUOI", "muc_giam_ty_le": 0.15},
            {"doi_tuong": "NGUOI_KHUYET_TAT", "muc_giam_ty_le": 0.25},
            {"doi_tuong": "TRE_EM", "muc_giam_ty_le": 0.10},
            {"doi_tuong": "NGUOI_CO_CONG", "muc_giam_ty_le": 0.30},
        ],
        "policy_version": 1,
    }


def build_forecast(bookings):
    """forecast_remaining_demand model-backed (nguồn: CALIB["intensity"], xem
    integration/forecast_seed_ref.py::build_forecast_calibrated) — thay hệ số ×0.6 phẳng
    cũ (đồng đều mọi đoạn, mất tín hiệu khan hiếm theo đoạn)."""
    sold_by_segment = {s: 0 for s in range(1, 8)}
    for b in bookings:
        for s in b["segments"]:
            sold_by_segment[s] += 1
    intensity = {int(k): v for k, v in CALIB["intensity"].items()}
    confidence = CALIB["confidence"]  # nguồn: CALIB["confidence_source"]
    forecasts = []
    for s in range(1, 8):
        remaining_cap = N_SEATS - sold_by_segment[s]
        expected_final = intensity[s] * N_SEATS
        remaining_demand = max(expected_final - sold_by_segment[s], 0.0)
        forecasts.append({
            "segment_id": s,
            "seat_class": SEAT_CLASS,
            "remaining_capacity": remaining_cap,
            "forecast_remaining_demand": round(remaining_demand, 1),
            "confidence": confidence,
        })
    return {"service_run_id": SERVICE_RUN_ID, "forecast_version": 1, "segments": forecasts}


def sha256_of(obj) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main():
    SEED_DIR.mkdir(exist_ok=True)
    (SEED_DIR / "backtest").mkdir(exist_ok=True)

    calib = calibrate()
    scenario = build_scenario()
    bookings = build_initial_bookings()
    fare_products = build_fare_products(calib)
    pricing_policy = build_pricing_policy(calib)
    forecast = build_forecast(bookings)

    (SEED_DIR / "scenario.json").write_text(
        json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")

    with (SEED_DIR / "initial_bookings.jsonl").open("w", encoding="utf-8") as f:
        for b in bookings:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

    (SEED_DIR / "fare_products.json").write_text(
        json.dumps({"service_run_id": SERVICE_RUN_ID, "products": fare_products}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    (SEED_DIR / "pricing_policy.json").write_text(
        json.dumps(pricing_policy, ensure_ascii=False, indent=2), encoding="utf-8")

    (SEED_DIR / "forecast.json").write_text(
        json.dumps(forecast, ensure_ascii=False, indent=2), encoding="utf-8")

    checksums = {
        "scenario_checksum": sha256_of(scenario),
        "initial_bookings_checksum": sha256_of(bookings),
        "fare_products_checksum": sha256_of(fare_products),
        "pricing_policy_checksum": sha256_of(pricing_policy),
        "forecast_checksum": sha256_of(forecast),
    }
    # Gộp checksum event stream backtest của BE2 vào manifest tổng (progress.md dòng 109)
    bt_manifest = SEED_DIR / "backtest" / "checksums.json"
    if bt_manifest.exists():
        checksums["backtest_events_checksums"] = json.loads(
            bt_manifest.read_text(encoding="utf-8"))["checksums"]
    (SEED_DIR / "expected_checksums.json").write_text(
        json.dumps(checksums, ensure_ascii=False, indent=2), encoding="utf-8")

    print("seed/ built:")
    for f in sorted(SEED_DIR.rglob("*")):
        if f.is_file():
            print(" -", f.relative_to(SEED_DIR))
    golden = [b for b in bookings if b["seat_id"] == GOLDEN_SEAT]
    print("golden seat bookings:", golden)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""OFFLINE, chạy 1 lần (cần generated_data/data/, pandas) — tính target_occ + intensity
theo golden segment từ dataset thật, ghi ra backend/scripts/calibration_cache.json để
build_seed.py đọc (không import pandas ở đó, giữ invariant dataset != runtime).

Nguồn: generated_data/data/transactions/thang=2026-06/part.parquet (đã bán, loai_cho
NGOI_MEM_DH, chuyến SE1 LE) + search_log cùng tháng (TU_CHOI_HET_CHO = cầu bị từ chối
hết chỗ). Cửa sổ 2026-06-08..2026-06-22 (trung tuần 06/2026, quanh golden date 06-15)
để đủ mẫu, không lấy đúng 1 ngày (nhiễu cao).

occ[s]       = sold_NGOI_MEM_DH phủ segment s / cap_NGOI_MEM_DH (168, SE1 LE, trains.csv)
intensity[s] = (sold_NGOI_MEM_DH[s] + unmet_scaled[s]) / cap_NGOI_MEM_DH
  unmet_scaled = unmet tổng (mọi hạng, search_log không phân hạng) x (cap_NGOI_MEM_DH/suc_chua)
  — xấp xỉ tỷ trọng hạng ghế trong cầu bị từ chối, cách làm hợp lý duy nhất khi search_log
  không có cột hạng ghế.
"""
import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent.parent
DATA = BASE / "generated_data" / "data"
OUT = Path(__file__).resolve().parent / "calibration_cache.json"

GOLDEN_STATIONS = ["HNO", "NBI", "THO", "VIN", "DHO", "HUE", "DNA", "SGO"]
DATE_LO, DATE_HI = "2026-06-08", "2026-06-22"
TRAIN, CHIEU, SEAT_CLASS = "SE1", "LE", "NGOI_MEM_DH"


def main():
    stations = pd.read_csv(DATA / "stations.csv").set_index("ga_id")["ly_trinh_km"]
    trains = pd.read_csv(DATA / "trains.csv")
    row = trains[(trains.mac_tau == TRAIN) & (trains.chieu == CHIEU)].iloc[0]
    cap_class, cap_total = int(row["cap_NGOI_MEM_DH"]), int(row["suc_chua"])

    txn = pd.read_parquet(DATA / "transactions" / "thang=2026-06" / "part.parquet")
    txn = txn[(txn.mac_tau == TRAIN) & (txn.ngay_chay.between(DATE_LO, DATE_HI))
              & (txn.trang_thai == "HIEU_LUC")]
    txn_class = txn[txn.loai_cho == SEAT_CLASS].copy()
    txn_class["o_km"] = txn_class.ga_di.map(stations)
    txn_class["d_km"] = txn_class.ga_den.map(stations)

    search = pd.read_parquet(DATA / "search_log" / "thang=2026-06" / "part.parquet")
    search = search[search.chuyen_id.str.startswith(TRAIN + "_")
                     & search.ngay_di.between(DATE_LO, DATE_HI)
                     & (search.ket_qua == "TU_CHOI_HET_CHO")].copy()
    search["o_km"] = search.ga_di.map(stations)
    search["d_km"] = search.ga_den.map(stations)

    n_days = txn_class.ngay_chay.nunique() or 1
    occ, intensity = {}, {}
    for i in range(len(GOLDEN_STATIONS) - 1):
        seg_id = i + 1
        lo, hi = stations[GOLDEN_STATIONS[i]], stations[GOLDEN_STATIONS[i + 1]]
        sold = txn_class[(txn_class.o_km <= lo) & (txn_class.d_km >= hi)]
        sold_per_day = len(sold) / n_days
        unmet = search[(search.o_km <= lo) & (search.d_km >= hi)]
        unmet_per_day = len(unmet) / n_days
        unmet_scaled = unmet_per_day * (cap_class / cap_total)

        occ[seg_id] = round(min(sold_per_day / cap_class, 1.0), 4)
        intensity[seg_id] = round((sold_per_day + unmet_scaled) / cap_class, 4)

    spec = json.loads((BASE / "models" / "artifacts" / "bt1_feature_spec.json").read_text(encoding="utf-8"))
    mase = spec["metrics"]["MASE_model"]
    confidence = round(1 - mase / 2, 2)  # nguồn: models/artifacts/bt1_feature_spec.json metrics.MASE_model

    out = {
        "source": f"transactions+search_log thang=2026-06, {TRAIN} {CHIEU}, "
                   f"{DATE_LO}..{DATE_HI} ({n_days} ngày), NGOI_MEM_DH cap={cap_class}/{cap_total}",
        "target_occ": occ,
        "intensity": intensity,
        "confidence": confidence,
        "confidence_source": f"1 - MASE_model/2, MASE_model={mase} (models/artifacts/bt1_feature_spec.json)",
        "rho_t": float(row["rho_t"]),
        "rho_t_source": "generated_data/data/trains.csv row SE1/LE",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""OFFLINE (cần generated_data/data/, pandas) — tính λ thật per O-D golden (8 ga) cho
backtest event stream, thay `TARGET_TOTAL_REQUESTS=400` bịa cũ trong
`backend/src/backtest/events.py`.

λ[(o,d)] = (tổng số search request cho đúng cặp ga (o,d) golden, suốt đợt bán 1 chuyến
SE1 LE, trung bình qua các chuyến 06-08..06-22/2026) × 40/448 (tỷ lệ sức chứa 40 ghế
golden / suc_chua thật SE1). search_log không tách theo hạng ghế nên coi cầu đồng nhất
theo hạng — dùng 40/448 trên TOÀN BỘ demand, không riêng NGOI_MEM_DH.
"""
import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent.parent
DATA = BASE / "generated_data" / "data"
OUT = Path(__file__).resolve().parent / "backtest_lambda_cache.json"

GOLDEN_STATIONS = ["HNO", "NBI", "THO", "VIN", "DHO", "HUE", "DNA", "SGO"]
TRAIN = "SE1"
DATE_LO, DATE_HI = "2026-06-08", "2026-06-22"
N_SEATS, CAP_TOTAL = 40, 448  # cap_total: trains.csv suc_chua SE1


def main():
    s = pd.read_parquet(DATA / "search_log" / "thang=2026-06" / "part.parquet")
    s = s[s.chuyen_id.str.startswith(TRAIN + "_") & s.ngay_di.between(DATE_LO, DATE_HI)
          & s.ga_di.isin(GOLDEN_STATIONS) & s.ga_den.isin(GOLDEN_STATIONS)]
    n_days = s.ngay_di.nunique()
    grp = s.groupby(["ga_di", "ga_den"]).size() / n_days  # avg total request/departure

    lambda_per_day_scaled = {
        f"{o}|{d}": round(v * N_SEATS / CAP_TOTAL, 4) for (o, d), v in grp.items()
    }
    out = {
        "lambda_per_day_scaled": lambda_per_day_scaled,
        "source": f"search_log thang=2026-06, {TRAIN}, {DATE_LO}..{DATE_HI} "
                  f"({n_days} chuyến), scale {N_SEATS}/{CAP_TOTAL}",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

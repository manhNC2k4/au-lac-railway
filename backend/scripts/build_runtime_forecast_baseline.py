#!/usr/bin/env python3
"""Build compact, leakage-safe future inference features from the input dataset.

The runtime image does not carry the 1.1 GB source export. This script reduces
the final 28 available SE1 departure dates to one feature baseline per O-D and
macro seat class. The generated JSON is small enough to ship with the backend.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

CLASS_MAP = {"NGOI_MEM_DH": "NGOI", "NAM_K6": "K6", "NAM_K4": "K4"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cutoff", default="2026-06-30")
    args = parser.parse_args()

    cutoff = pd.Timestamp(args.cutoff)
    start = cutoff - pd.Timedelta(days=27)
    tx = pd.read_parquet(
        args.data / "transactions" / "thang=2026-06",
        columns=["mac_tau", "ngay_chay", "ga_di", "ga_den", "loai_cho",
                 "lead_time_ngay", "trang_thai"],
    )
    tx["ngay_chay"] = pd.to_datetime(tx["ngay_chay"])
    tx = tx[
        tx.mac_tau.eq("SE1")
        & tx.trang_thai.eq("HIEU_LUC")
        & tx.ngay_chay.between(start, cutoff)
    ].copy()
    tx["seat_class"] = tx.loai_cho.map(CLASS_MAP)
    tx = tx[tx.seat_class.notna()]
    tx["at_u14"] = tx.lead_time_ngay.ge(14).astype(int)
    tx["pickup_7d"] = tx.lead_time_ngay.between(14, 21).astype(int)

    stations = pd.read_csv(args.data / "stations.csv").sort_values("ly_trinh_km")
    station_ids = stations.ga_id.tolist()
    km = dict(zip(stations.ga_id, stations.ly_trinh_km.astype(float)))
    dates = pd.date_range(start, cutoff, freq="D")
    keys = [
        (origin, dest, model_class)
        for i, origin in enumerate(station_ids)
        for dest in station_ids[i + 1:]
        for model_class in CLASS_MAP.values()
    ]

    daily = tx.groupby(
        ["ngay_chay", "ga_di", "ga_den", "seat_class"], observed=True
    ).agg(
        q_final=("lead_time_ngay", "size"),
        da_ban_truoc_u14=("at_u14", "sum"),
        toc_do_ban_7d=("pickup_7d", "sum"),
    )

    records = []
    for origin, dest, model_class in keys:
        frame = pd.DataFrame(
            {"q_final": 0, "da_ban_truoc_u14": 0, "toc_do_ban_7d": 0},
            index=dates,
        )
        try:
            values = daily.xs((origin, dest, model_class), level=("ga_di", "ga_den", "seat_class"))
            frame.update(values)
        except KeyError:
            pass
        frame = frame.fillna(0)
        records.append({
            "origin": origin,
            "dest": dest,
            "model_seat_class": model_class,
            "runtime_seat_class": {v: k for k, v in CLASS_MAP.items()}[model_class],
            "cu_ly_km": round(km[dest] - km[origin], 1),
            "da_ban_truoc_u14": round(float(frame.da_ban_truoc_u14.mean()), 4),
            "toc_do_ban_7d": round(float(frame.toc_do_ban_7d.mean()), 4),
            "q_lag_7": int(frame.q_final.iloc[-8]),
            "rolling_mean_28": round(float(frame.q_final.mean()), 4),
        })

    payload = {
        "source": "v2-as-v1/data/transactions/thang=2026-06",
        "train_id": "SE1",
        "cutoff": args.cutoff,
        "window_start": start.strftime("%Y-%m-%d"),
        "window_days": 28,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(records)} feature rows to {args.output}")


if __name__ == "__main__":
    main()

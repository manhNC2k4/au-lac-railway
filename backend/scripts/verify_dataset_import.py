#!/usr/bin/env python3
"""Verify the runtime database against the compatibility input dataset."""
from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal
from pathlib import Path

from src.state.db import get_connection

REFERENCE_RUN_ID = "RUN:SE1:2026-06-30"
SEAT_CLASSES = ("NGOI_MEM_DH", "NAM_K6", "NAM_K4")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    data_dir = args.dataset / "data"

    source_stations = read_csv(data_dir / "stations.csv")
    source_train = next(row for row in read_csv(data_dir / "trains.csv") if row["mac_tau"] == "SE1")
    source_inventory = [
        row for row in read_csv(data_dir / "seat_inventory.csv")
        if row["chuyen_id"] == REFERENCE_RUN_ID
    ]

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT station_id, station_name, ly_trinh_km, station_type,
                      dwell_minutes, province_2025, effective_from::text
                 FROM station ORDER BY ly_trinh_km"""
        )
        db_stations = cur.fetchall()
        cur.execute(
            """SELECT train_id, direction, origin_station_id, dest_station_id,
                      departure_time::text, revenue_coefficient, capacity
                 FROM train WHERE train_id='SE1'"""
        )
        db_train = cur.fetchone()
        cur.execute(
            """SELECT seat_class, capacity FROM train_seat_class
                WHERE train_id='SE1' ORDER BY seat_class"""
        )
        db_capacities = dict(cur.fetchall())
        cur.execute(
            """SELECT segment_id, seat_class, capacity, sold
                 FROM inventory_reference_profile
                WHERE reference_run_id=%s ORDER BY segment_id, seat_class""",
            (REFERENCE_RUN_ID,),
        )
        db_inventory = cur.fetchall()
        cur.execute(
            """SELECT sr.service_run_id, sss.seat_class, COUNT(DISTINCT sss.seat_id),
                      COUNT(DISTINCT sss.segment_id)
                 FROM service_run sr
                 JOIN seat_segment_state sss ON sss.service_run_id=sr.service_run_id
                WHERE sr.data_source='MODEL_SIMULATION'
                GROUP BY sr.service_run_id, sss.seat_class
                ORDER BY sr.service_run_id, sss.seat_class"""
        )
        runtime_shapes = cur.fetchall()
    conn.commit()
    conn.close()

    expected_stations = [(
        row["ga_id"], row["ten_ga"], Decimal(row["ly_trinh_km"]), row["loai_ga"],
        int(row["dwell_phut"]), row["tinh_2025"], row["hieu_luc_tu"],
    ) for row in source_stations]
    expected_train = (
        "SE1", source_train["chieu"], source_train["ga_dau"], source_train["ga_cuoi"],
        f'{source_train["gio_xp"]}:00', Decimal(source_train["rho_t"]), int(source_train["suc_chua"]),
    )
    expected_capacities = {seat_class: int(source_train[f"cap_{seat_class}"]) for seat_class in SEAT_CLASSES}
    expected_inventory = [(
        int(row["khu_gian_id"]), row["loai_cho"], int(row["suc_chua"]),
        int(row["da_ban"]),
    ) for row in source_inventory]

    checks = {
        "stations_25_exact": db_stations == expected_stations,
        "train_se1_exact": db_train == expected_train,
        "seat_class_capacity_exact": db_capacities == expected_capacities,
        "reference_inventory_72_exact": db_inventory == expected_inventory,
        "runtime_matrix_shape": bool(runtime_shapes) and all(
            seats == expected_capacities[seat_class] and segments == 24
            for _, seat_class, seats, segments in runtime_shapes
        ),
    }
    report = {
        "dataset": str(args.dataset),
        "reference_run_id": REFERENCE_RUN_ID,
        "checks": checks,
        "runtime_run_count": len({row[0] for row in runtime_shapes}),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

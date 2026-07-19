# -*- coding: utf-8 -*-
"""Persist model-generated O-D forecasts for dataset-compatible future runs."""
from __future__ import annotations

import json
from pathlib import Path

from ..api.deps import get_clock, get_demand_model
from ..state.db import get_connection
from ..state.errors import PolicyUnavailable
from .topology import get_run_topology

BASELINE_PATH = Path(__file__).resolve().parents[2] / "seed" / "runtime_forecast_baseline.json"


def ensure_model_forecast(service_run_id: str) -> int:
    topology = get_run_topology(service_run_id)
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT MAX(forecast_version) FROM demand_forecast
                WHERE service_run_id=%s AND data_source='MODEL_HGB'""",
            (service_run_id,),
        )
        existing = cur.fetchone()[0]
    conn.commit()
    if existing is not None:
        return int(existing)
    if topology["data_source"] != "MODEL_SIMULATION":
        return 1
    if not BASELINE_PATH.exists():
        raise PolicyUnavailable("Thiếu runtime_forecast_baseline.json", {})

    from integration.runtime_forecast import predict_future_demand

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    rows = predict_future_demand(
        get_demand_model(), baseline["records"], topology["service_date"], get_clock().now().date()
    )
    version = 1
    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """INSERT INTO demand_forecast
                   (service_run_id, origin_station_id, dest_station_id, seat_class,
                    forecast_demand, confidence_score, forecast_version,
                    data_source, feature_snapshot)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'MODEL_HGB',%s)""",
                (service_run_id, row["origin"], row["dest"], row["runtime_seat_class"],
                 round(row["forecast_demand"]), row["confidence"], version,
                 json.dumps(row["feature_snapshot"], ensure_ascii=False)),
            )
    conn.commit()
    return version

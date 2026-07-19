"""Pandas-backed future forecast inference outside backend/src.

The backend passes compact feature records and the already loaded DemandModel.
This module owns DataFrame construction so request modules stay data-frame free.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
from lunardate import LunarDate


def _nearest_tet_days(service_date: date) -> int:
    anchors = [LunarDate(year, 1, 1).toSolarDate() for year in range(service_date.year - 1, service_date.year + 2)]
    return min(((service_date - anchor).days for anchor in anchors), key=abs)


def _band(distance_km: float) -> str:
    if distance_km <= 300:
        return "ngan"
    if distance_km <= 900:
        return "trung"
    return "dai"


def predict_future_demand(model, baseline_records: list[dict], service_date: date,
                          today: date) -> list[dict]:
    lead_time = max((service_date - today).days, 0)
    tau_tet = _nearest_tet_days(service_date)
    is_tet = abs(tau_tet) <= 21
    rows = []
    for source in baseline_records:
        rows.append({
            **source,
            "mac_tau": "SE1",
            "ga_di": source["origin"],
            "ga_den": source["dest"],
            "seat_class": source["model_seat_class"],
            "band": _band(float(source["cu_ly_km"])),
            "dot_ban_ve": f"TET_{service_date.year}" if is_tet else "THUONG",
            # The artifact vocabulary was fitted on the pre-AI regime and contains
            # only LUAT. Pricing mode remains AI; this field is the forecast regime.
            "che_do_gia": "LUAT",
            "dow": str(service_date.weekday()),
            "tau_tet": tau_tet,
            "la_le": int(is_tet),
            "H_horizon": 127,
            "sau_15_5": int(service_date >= date(2026, 5, 15)),
        })

    totals = model.fc.predict(pd.DataFrame(rows))
    output = []
    for row, total in zip(rows, totals):
        F_u = model._F(row["band"], is_tet, lead_time)
        remaining = max(float(total) * (1.0 - F_u), 0.0)
        feature_snapshot = {key: row[key] for key in model.fc.cat_cols + model.fc.num_cols}
        output.append({
            "origin": row["origin"],
            "dest": row["dest"],
            "runtime_seat_class": row["runtime_seat_class"],
            "forecast_demand": round(remaining, 3),
            "confidence": round(0.5 + 0.5 * F_u, 4),
            "feature_snapshot": feature_snapshot,
        })
    return output

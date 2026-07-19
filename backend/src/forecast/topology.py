# -*- coding: utf-8 -*-
"""Run topology loaded from DB, with a compatibility path for the 40x7 golden run."""
from __future__ import annotations

from ..state.db import get_connection
from ..state.errors import NoSameSeatOption, ResourceNotFound
from . import network


def get_run_topology(service_run_id: str) -> dict:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT train_id, service_date, direction, model_run_id, data_source FROM service_run WHERE service_run_id=%s",
            (service_run_id,),
        )
        run = cur.fetchone()
        if run is None:
            conn.rollback()
            raise ResourceNotFound("Không tìm thấy chuyến", {"service_run_id": service_run_id})
        if run[4] == "MODEL_SIMULATION":
            cur.execute(
                """SELECT ts.stop_sequence, ts.station_id, s.station_name,
                          s.ly_trinh_km, COALESCE(s.dwell_minutes,0)
                     FROM train_stop ts JOIN station s ON s.station_id=ts.station_id
                    WHERE ts.train_id=%s ORDER BY ts.stop_sequence""",
                (run[0],),
            )
            rows = cur.fetchall()
        else:
            rows = []
    conn.commit()

    if rows:
        stations = [{"sequence": r[0], "id": r[1], "name": r[2],
                     "km": float(r[3]), "dwell_minutes": float(r[4])} for r in rows]
    else:
        stations = [{"sequence": i + 1, "id": item["id"], "name": item["id"],
                     "km": float(item["km"]),
                     "dwell_minutes": float(network.DWELL_MINUTES.get(item["id"], 0))}
                    for i, item in enumerate(network.STATIONS)]
    return {
        "service_run_id": service_run_id,
        "train_id": run[0],
        "service_date": run[1],
        "direction": run[2],
        "model_run_id": run[3] or service_run_id,
        "data_source": run[4],
        "stations": stations,
        "n_segments": len(stations) - 1,
    }


def segment_span(topology: dict, origin: str, dest: str) -> tuple[int, int]:
    ids = [station["id"] for station in topology["stations"]]
    if origin not in ids or dest not in ids:
        raise NoSameSeatOption("Ga ngoài tuyến tàu", {"origin": origin, "dest": dest})
    start, end = ids.index(origin), ids.index(dest)
    if start >= end:
        raise NoSameSeatOption("Ga đi phải đứng trước ga đến theo chiều chạy", {"origin": origin, "dest": dest})
    return start + 1, end


def distance_km(topology: dict, origin: str, dest: str) -> float:
    by_id = {station["id"]: station["km"] for station in topology["stations"]}
    return abs(by_id[dest] - by_id[origin])

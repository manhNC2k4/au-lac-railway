# -*- coding: utf-8 -*-
"""GET /demo/{overview,seatmap,analytics} (read-only) + POST reset/forecasts-refresh."""
from fastapi import APIRouter, Depends

from .deps import SEED_DIR, get_state_manager
from .schemas import ResetRequest

router = APIRouter(tags=["demo"])


@router.post("/demo/scenarios/{scenario_id}/reset")
def reset_scenario(scenario_id: str, body: ResetRequest = ResetRequest()):
    ssm = get_state_manager()
    result = ssm.reset_scenario(SEED_DIR)
    return {"data": result, "message": "Scenario reset successfully"}


@router.post("/demo/forecasts/refresh")
def refresh_forecast(body: dict):
    # BE2 territory (logic forecast) — route stub trả forecast_version hiện tại
    # vì seed/forecast.json là forecast_version=1 tĩnh trong phiên này.
    return {"message": "Forecast updated", "data": {"forecast_version": 1}}


@router.get("/demo/overview")
def get_overview(service_run_id: str):
    ssm = get_state_manager()
    seatmap = ssm.get_seatmap(service_run_id)
    n_segments = max((int(s) for seat in seatmap["seats"].values() for s in seat), default=0)
    occ_by_seg: dict[int, list[int]] = {s: [0, 0] for s in range(1, n_segments + 1)}
    for seat_states in seatmap["seats"].values():
        for seg_str, status in seat_states.items():
            seg = int(seg_str)
            occ_by_seg[seg][1] += 1
            if status != "FREE":
                occ_by_seg[seg][0] += 1
    occupancy = {s: (sold / total if total else 0.0) for s, (sold, total) in occ_by_seg.items()}
    overall = sum(o for o in occupancy.values()) / len(occupancy) if occupancy else 0.0
    bottlenecks = sorted(occupancy.items(), key=lambda kv: -kv[1])[:3]
    underused = sorted(occupancy.items(), key=lambda kv: kv[1])[:3]
    return {"data": {
        "overall_occupancy": round(overall, 3),
        "total_revenue_vnd": 0,
        "empty_seat_km": 0,
        "passenger_km": 0,
        "false_sold_out_rate": 0.0,
        "bottlenecks": [{"segment_id": s, "occupancy": round(o, 3)} for s, o in bottlenecks],
        "underused": [{"segment_id": s, "occupancy": round(o, 3)} for s, o in underused],
        "recent_decisions": [],
    }}


@router.get("/demo/seatmap")
def get_seatmap(service_run_id: str):
    ssm = get_state_manager()
    result = ssm.get_seatmap(service_run_id)
    seats_out = []
    for seat_id, states in sorted(result["seats"].items()):
        seats_out.append({"seat_id": seat_id, "seat_class": "NGOI_MEM_DH", "states": states})
    return {"data": {"matrix_version": result["matrix_version"], "seats": seats_out}}


@router.get("/demo/analytics")
def get_analytics(service_run_id: str):
    ssm = get_state_manager()
    seatmap = ssm.get_seatmap(service_run_id)
    n_segments = max((int(s) for seat in seatmap["seats"].values() for s in seat), default=0)
    remaining: dict[int, int] = {s: 0 for s in range(1, n_segments + 1)}
    for seat_states in seatmap["seats"].values():
        for seg_str, status in seat_states.items():
            if status == "FREE":
                remaining[int(seg_str)] += 1
    segment_loads = [{"segment_id": s, "remaining_capacity": remaining[s]} for s in sorted(remaining)]
    return {"data": {"forecasts": [], "segment_loads": segment_loads, "allocations": []}}

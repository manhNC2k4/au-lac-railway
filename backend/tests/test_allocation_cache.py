# -*- coding: utf-8 -*-
"""P2 Bước4 — `allocation.cache` khớp gọi tay `app.bt3_allocation.analyze_run`,
và phản ứng đúng (dual > 0) khi cầu vượt sức chứa còn lại."""
import json

import pandas as pd
import pytest

from src.adapters import model_adapter
from src.allocation import cache as allocation_cache
from src.api import deps
from src.api.deps import SEED_DIR, get_pricer, get_state_manager
from src.forecast import network
from src.state.db import get_connection

SERVICE_RUN_ID = "SE1_2026-06-15_LE"


@pytest.fixture(autouse=True, scope="module")
def _load_models_once():
    deps.load_models()


@pytest.fixture(autouse=True)
def _reset():
    get_state_manager().reset_scenario(SEED_DIR)
    yield


def test_cache_matches_manual_analyze_run():
    from app.bt3_allocation import analyze_run
    from integration.ssm_from_postgres import build_shim

    result = allocation_cache.refresh(SERVICE_RUN_ID)
    assert result is not None

    scenario = json.loads((SEED_DIR / "scenario.json").read_text(encoding="utf-8"))
    seatmap = get_state_manager().get_seatmap(SERVICE_RUN_ID)
    matrix, _seat_ids = model_adapter.seatmap_to_matrix(seatmap, network.N_SEGMENTS)
    shim = build_shim(scenario, matrix)

    # Đọc forecast từ DB (đã ROUND lúc reset_scenario) — khớp đúng input mà
    # cache.refresh dùng, chứ không phải giá trị thô chưa làm tròn trong seed/forecast.json.
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT forecast_demand FROM demand_forecast
               WHERE service_run_id=%s AND seat_class='NGOI_MEM_DH' ORDER BY id""",
            (SERVICE_RUN_ID,),
        )
        demand_rows = cur.fetchall()
    conn.commit()
    segs = scenario["segments"]
    fc_rows = [{"origin": s["from"], "dest": s["to"], "seat_class": "NGOI_MEM_DH",
                "remaining_demand": float(demand_rows[i][0])}
               for i, s in enumerate(segs)]
    manual = analyze_run(shim, get_pricer(), shim.chuyen_id, pd.DataFrame(fc_rows))

    assert result["bid_price_theo_lop"] == manual["bid_price_theo_lop"]
    assert result["z_opt_dlp"] == manual["z_opt_dlp"]


def test_cache_get_returns_none_for_unknown_version():
    allocation_cache.refresh(SERVICE_RUN_ID)
    assert allocation_cache.get(SERVICE_RUN_ID, 999, 999) is None


def test_bid_price_positive_when_demand_exceeds_remaining_capacity():
    """Seed forecast (3.6-16.2) < sức chứa còn lại mọi đoạn ⇒ dual=0 hết (xem
    test_api_e2e.py::test_offer_golden_gap_accept). Ép forecast mới demand=999
    (>> sức chứa 40) ⇒ mọi đoạn nghẽn ⇒ dual > 0 — chứng minh LP thật sự chạy,
    không phải luôn trả 0."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(MAX(forecast_version),1) FROM demand_forecast WHERE service_run_id=%s",
            (SERVICE_RUN_ID,),
        )
        new_version = cur.fetchone()[0] + 1
        for _ in range(network.N_SEGMENTS):
            cur.execute(
                """INSERT INTO demand_forecast
                   (service_run_id, origin_station_id, dest_station_id, seat_class,
                    forecast_demand, confidence_score, forecast_version)
                   VALUES (%s,NULL,NULL,%s,%s,%s,%s)""",
                (SERVICE_RUN_ID, "NGOI_MEM_DH", 999, 0.9, new_version),
            )
    conn.commit()

    result = allocation_cache.refresh(SERVICE_RUN_ID)
    assert result is not None
    assert any(v > 0 for v in result["bid_price_theo_lop"]["NGOI_MEM_DH"])

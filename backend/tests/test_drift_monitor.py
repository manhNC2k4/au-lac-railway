# -*- coding: utf-8 -*-
"""P7.5 — drift monitor: forecasts/refresh phải persist divergence vào proposal_log
và GET /demo/overview phải trả cảnh báo (|divergence| >= app.reallocation.DIV_THRESHOLD)."""
from tests.test_api_e2e import BASE, SERVICE_RUN_ID, client, scenario  # noqa: F401 (fixture reuse)


def test_refresh_persists_forecast_drift_log(scenario, conn):
    r = client.post(f"{BASE}/demo/forecasts/refresh", json={"service_run_id": SERVICE_RUN_ID})
    assert r.status_code == 200
    assert "drift_alerts" in r.json()["data"]

    with conn.cursor() as cur:
        cur.execute(
            """SELECT loai, output FROM proposal_log WHERE service_run_id=%s AND loai='FORECAST'
               ORDER BY id DESC LIMIT 1""",
            (SERVICE_RUN_ID,),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    assert "divergence_by_segment" in row[1]
    assert "alerts" in row[1]


def test_overview_surfaces_drift_alerts_field(scenario):
    client.post(f"{BASE}/demo/forecasts/refresh", json={"service_run_id": SERVICE_RUN_ID})
    r = client.get(f"{BASE}/demo/overview", params={"service_run_id": SERVICE_RUN_ID})
    assert r.status_code == 200
    assert "drift_alerts" in r.json()["data"]

# -*- coding: utf-8 -*-
"""P7.4 (C4 xếp nhóm) — POST /group/quote đề xuất ghế cùng toa cho nhóm, thuần đề
xuất (không giữ ghế), persist ProposalLog."""
from tests.test_api_e2e import BASE, SERVICE_RUN_ID, client, scenario  # noqa: F401


def test_group_quote_feasible_same_car(scenario, conn):
    r = client.post(f"{BASE}/group/quote", json={
        "service_run_id": SERVICE_RUN_ID, "origin_station_id": "HNO", "dest_station_id": "NBI",
        "seat_class": "NGOI_MEM_DH", "n_khach": 8,
    })
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["kha_thi"] is True
    assert len(d["assignments"]) == 8
    assert all("seat_id" in a for a in d["assignments"])
    assert len(d["toa"]) == 1               # 8 khách, còn nguyên 40 ghế trống -> gọn 1 toa

    with conn.cursor() as cur:
        cur.execute(
            "SELECT loai FROM proposal_log WHERE service_run_id=%s AND loai='GROUP' ORDER BY id DESC LIMIT 1",
            (SERVICE_RUN_ID,),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None


def test_group_quote_infeasible_too_many(scenario):
    r = client.post(f"{BASE}/group/quote", json={
        "service_run_id": SERVICE_RUN_ID, "origin_station_id": "THO", "dest_station_id": "DHO",
        "seat_class": "NGOI_MEM_DH", "n_khach": 100,
    })
    assert r.status_code == 422
    assert r.json()["error_code"] == "NO_SAME_SEAT_OPTION"

# -*- coding: utf-8 -*-
"""Fix P7-follow-up: hold_multi()/expire_due_holds() bump matrix_version nhưng KHÔNG tự
refresh cache DLP (allocation/cache.py) — trước fix, /offers ngay sau 1 hold (matrix_version
đổi) sẽ 503 POLICY_UNAVAILABLE giả vì cache miss, dù DLP hoàn toàn giải được. routes_offers.py
giờ tự refresh 1 lần khi cache miss trước khi 503 hẳn."""
from tests.test_api_e2e import BASE, SERVICE_RUN_ID, client, scenario  # noqa: F401

SEAT_CLASS = "NGOI_MEM_DH"


def test_offer_survives_matrix_version_bump_from_hold(scenario):
    # 1) Offer + hold đầu tiên -> bump matrix_version (giống việc waitlist/match tự tạo hold)
    off1 = client.post(f"{BASE}/offers", json={
        "service_run_id": SERVICE_RUN_ID, "origin_station_id": "HNO", "dest_station_id": "NBI",
        "seat_class": SEAT_CLASS, "quantity": 1, "priority_passenger": False,
    }).json()["data"]
    hold1 = client.post(f"{BASE}/holds", json={
        "offer_id": off1["offer_id"], "expected_matrix_version": off1["matrix_version"],
    }, headers={"Idempotency-Key": "staleness-test-hold-1"})
    assert hold1.status_code == 201, hold1.text
    assert hold1.json()["data"]["new_matrix_version"] == off1["matrix_version"] + 1

    # 2) Offer THỨ HAI ngay sau, matrix_version đã đổi — trước fix: 503 POLICY_UNAVAILABLE giả
    off2 = client.post(f"{BASE}/offers", json={
        "service_run_id": SERVICE_RUN_ID, "origin_station_id": "VIN", "dest_station_id": "DHO",
        "seat_class": SEAT_CLASS, "quantity": 1, "priority_passenger": False,
    })
    assert off2.status_code == 201, off2.text
    assert off2.json()["data"]["decision"] == "ACCEPT"
    assert off2.json()["data"]["matrix_version"] == off1["matrix_version"] + 1

# -*- coding: utf-8 -*-
"""P7.3 (C5 hàng chờ thông minh) — add trả score hợp lệ; match tạo Offer+Hold THẬT
(tái dùng pipeline /offers->/holds) khi có ghế, giữ PENDING khi chưa có ghế."""
from tests.test_api_e2e import BASE, SERVICE_RUN_ID, client, scenario  # noqa: F401

SEAT_CLASS = "NGOI_MEM_DH"


def test_add_returns_pending_with_score(scenario):
    r = client.post(f"{BASE}/waitlist", json={
        "service_run_id": SERVICE_RUN_ID, "origin_station_id": "HNO", "dest_station_id": "NBI",
        "seat_class": SEAT_CLASS, "u": 10,
    })
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["status"] == "PENDING"
    assert 0.0 <= d["priority_score"] <= 1.0

    pend = client.get(f"{BASE}/waitlist", params={"service_run_id": SERVICE_RUN_ID}).json()["data"]["pending"]
    assert any(p["waitlist_id"] == d["waitlist_id"] for p in pend)


def test_match_creates_real_hold_when_seat_available(scenario):
    add = client.post(f"{BASE}/waitlist", json={
        "service_run_id": SERVICE_RUN_ID, "origin_station_id": "HNO", "dest_station_id": "NBI",
        "seat_class": SEAT_CLASS, "u": 10,
    }).json()["data"]

    m = client.post(f"{BASE}/waitlist/match", params={"service_run_id": SERVICE_RUN_ID})
    assert m.status_code == 200, m.text
    matched = m.json()["data"]["matched"]
    assert any(x["waitlist_id"] == add["waitlist_id"] for x in matched)
    hold_id = next(x["hold_id"] for x in matched if x["waitlist_id"] == add["waitlist_id"])
    assert hold_id.startswith("hold_")

    pend = client.get(f"{BASE}/waitlist", params={"service_run_id": SERVICE_RUN_ID}).json()["data"]["pending"]
    assert not any(p["waitlist_id"] == add["waitlist_id"] for p in pend)


def test_match_leaves_entry_pending_when_no_seat(scenario, conn):
    # Ép đoạn 1 (HNO->NBI) hết chỗ hoàn toàn cho mọi ghế -> không thể khớp.
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE seat_segment_state SET status='SOLD' WHERE service_run_id=%s AND segment_id=1",
            (SERVICE_RUN_ID,),
        )
    conn.commit()

    add = client.post(f"{BASE}/waitlist", json={
        "service_run_id": SERVICE_RUN_ID, "origin_station_id": "HNO", "dest_station_id": "NBI",
        "seat_class": SEAT_CLASS, "u": 10,
    }).json()["data"]

    m = client.post(f"{BASE}/waitlist/match", params={"service_run_id": SERVICE_RUN_ID})
    assert m.status_code == 200
    matched_ids = [x["waitlist_id"] for x in m.json()["data"]["matched"]]
    assert add["waitlist_id"] not in matched_ids

    pend = client.get(f"{BASE}/waitlist", params={"service_run_id": SERVICE_RUN_ID}).json()["data"]["pending"]
    assert any(p["waitlist_id"] == add["waitlist_id"] for p in pend)

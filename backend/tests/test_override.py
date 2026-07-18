# -*- coding: utf-8 -*-
"""P7.6 — manual override: chỉ role revenue_manager/admin, chỉ TRONG guardrail, chỉ
khi offer chưa có hold (giá đã khoá bất khả xâm phạm)."""
from tests.test_api_e2e import BASE, SERVICE_RUN_ID, client, scenario  # noqa: F401

SEAT_CLASS = "NGOI_MEM_DH"


def _make_offer():
    r = client.post(f"{BASE}/offers", json={
        "service_run_id": SERVICE_RUN_ID, "origin_station_id": "HNO", "dest_station_id": "NBI",
        "seat_class": SEAT_CLASS, "quantity": 1, "priority_passenger": False,
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]


def test_override_requires_role_header(scenario):
    offer = _make_offer()
    r = client.post(f"{BASE}/offers/{offer['offer_id']}/override",
                    json={"new_price_vnd": offer["pricing"]["gia_niem_yet_vnd"], "reason": "test"},
                    headers={"X-Actor-Role": "user"})
    assert r.status_code == 403


def test_override_within_guardrail_succeeds(scenario, conn):
    offer = _make_offer()
    base_fare = offer["pricing"]["gia_goc_vnd"]
    new_price = round(base_fare * 1.0)   # bằng F0, chắc chắn trong [0.55, 1.60]*F0
    r = client.post(f"{BASE}/offers/{offer['offer_id']}/override",
                    json={"new_price_vnd": new_price, "reason": "khách VIP", "decided_by": "ops1"},
                    headers={"X-Actor-Role": "revenue_manager"})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["new_price_vnd"] == new_price

    with conn.cursor() as cur:
        cur.execute("SELECT final_price_vnd FROM offer WHERE offer_id=%s", (offer["offer_id"],))
        row = cur.fetchone()
    conn.commit()
    assert row[0] == new_price

    with conn.cursor() as cur:
        cur.execute(
            "SELECT loai, explain FROM proposal_log WHERE loai='OVERRIDE' ORDER BY id DESC LIMIT 1")
        log_row = cur.fetchone()
    conn.commit()
    assert log_row is not None
    assert "khách VIP" in log_row[1]


def test_override_outside_guardrail_rejected(scenario):
    offer = _make_offer()
    base_fare = offer["pricing"]["gia_goc_vnd"]
    r = client.post(f"{BASE}/offers/{offer['offer_id']}/override",
                    json={"new_price_vnd": base_fare * 5, "reason": "test"},
                    headers={"X-Actor-Role": "admin"})
    assert r.status_code == 422
    assert r.json()["error_code"] == "GUARDRAIL_VIOLATION"


def test_override_blocked_after_hold(scenario):
    offer = _make_offer()
    hold = client.post(f"{BASE}/holds", json={
        "offer_id": offer["offer_id"], "expected_matrix_version": offer["matrix_version"],
    }, headers={"Idempotency-Key": "test-override-hold-1"})
    assert hold.status_code == 201, hold.text

    r = client.post(f"{BASE}/offers/{offer['offer_id']}/override",
                    json={"new_price_vnd": offer["pricing"]["gia_goc_vnd"], "reason": "test"},
                    headers={"X-Actor-Role": "admin"})
    assert r.status_code == 409
    assert r.json()["error_code"] == "SEAT_CONFLICT"

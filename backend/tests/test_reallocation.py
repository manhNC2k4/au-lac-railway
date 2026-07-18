# -*- coding: utf-8 -*-
"""P7.2 (C2 tái phân bổ + phê duyệt + rollback) — propose tạo bản PENDING, approve
cần role revenue_manager/admin, rollback quay lại bản cũ."""
from tests.test_api_e2e import BASE, SERVICE_RUN_ID, client, scenario  # noqa: F401


def test_propose_creates_pending_version(scenario):
    r = client.post(f"{BASE}/allocation/refresh", params={"service_run_id": SERVICE_RUN_ID})
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["version"] == 1
    assert d["status"] == "PENDING"
    assert len(d["quota"]) == 7 * 3 * 3        # 7 đoạn x 3 loại hành trình x 3 lớp chỗ (analyze_run luôn quét cả 3)


def test_approve_requires_role_header(scenario):
    client.post(f"{BASE}/allocation/refresh", params={"service_run_id": SERVICE_RUN_ID})
    r = client.post(f"{BASE}/allocation/1/approve", params={"service_run_id": SERVICE_RUN_ID},
                    json={"decided_by": "someone"}, headers={"X-Actor-Role": "user"})
    assert r.status_code == 403
    assert r.json()["error_code"] == "FORBIDDEN"


def test_approve_then_rollback(scenario):
    v1 = client.post(f"{BASE}/allocation/refresh", params={"service_run_id": SERVICE_RUN_ID}).json()["data"]
    approve1 = client.post(f"{BASE}/allocation/{v1['version']}/approve",
                           params={"service_run_id": SERVICE_RUN_ID}, json={"decided_by": "ops1"},
                           headers={"X-Actor-Role": "revenue_manager"})
    assert approve1.status_code == 200
    assert approve1.json()["data"]["status"] == "ACTIVE"

    v2 = client.post(f"{BASE}/allocation/refresh", params={"service_run_id": SERVICE_RUN_ID}).json()["data"]
    approve2 = client.post(f"{BASE}/allocation/{v2['version']}/approve",
                           params={"service_run_id": SERVICE_RUN_ID}, json={"decided_by": "ops1"},
                           headers={"X-Actor-Role": "revenue_manager"})
    assert approve2.json()["data"]["status"] == "ACTIVE"

    # v1 phải bị lùi về ROLLED_BACK khi v2 được duyệt (chỉ 1 bản ACTIVE tại 1 thời điểm)
    got_v1 = client.get(f"{BASE}/allocation/{v1['version']}", params={"service_run_id": SERVICE_RUN_ID}).json()["data"]
    assert got_v1["status"] == "ROLLED_BACK"

    rb = client.post(f"{BASE}/allocation/{v1['version']}/rollback",
                     params={"service_run_id": SERVICE_RUN_ID}, json={"decided_by": "ops2"},
                     headers={"X-Actor-Role": "admin"})
    assert rb.status_code == 200
    assert rb.json()["data"]["status"] == "ACTIVE"
    got_v2 = client.get(f"{BASE}/allocation/{v2['version']}", params={"service_run_id": SERVICE_RUN_ID}).json()["data"]
    assert got_v2["status"] == "ROLLED_BACK"


def test_reject_pending_version(scenario):
    v1 = client.post(f"{BASE}/allocation/refresh", params={"service_run_id": SERVICE_RUN_ID}).json()["data"]
    r = client.post(f"{BASE}/allocation/{v1['version']}/reject",
                    params={"service_run_id": SERVICE_RUN_ID}, json={"decided_by": "ops1"},
                    headers={"X-Actor-Role": "revenue_manager"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "REJECTED"


def test_allocation_not_found(scenario):
    r = client.get(f"{BASE}/allocation/999", params={"service_run_id": SERVICE_RUN_ID})
    assert r.status_code == 404
    assert r.json()["error_code"] == "RESOURCE_NOT_FOUND"

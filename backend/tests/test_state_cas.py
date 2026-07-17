# -*- coding: utf-8 -*-
"""DoD tests — plan/DEV1_BE_STATE_INTEGRATION.md §"Test bắt buộc".
test_two_competing_holds_one_wins là test quan trọng nhất — viết trước CAS impl,
chứng minh G04 (atomic hold, 0 partial). Cần Postgres thật: docker compose up -d db flyway."""
from datetime import timedelta

import pytest

from src.state.clock import FixedClock
from src.state.db import get_connection
from src.state.errors import DomainError, HoldExpired, StaleSnapshot
from src.state.seat_state_manager import SeatStateManager

from tests.conftest import SERVICE_RUN_ID, insert_test_offer

GOLDEN_SEAT = "C01-S017"
GOLDEN_SEGMENTS = [3, 4]


def test_two_competing_holds_one_wins(reset_state, ssm, clock, conn):
    """1 hold thành công, 1 nhận lỗi 409, 0 partial hold — G04."""
    offer_a, offer_b = "offer_test_a", "offer_test_b"
    expires_at = clock.now() + timedelta(minutes=5)
    insert_test_offer(conn, offer_a, SERVICE_RUN_ID, expires_at)
    insert_test_offer(conn, offer_b, SERVICE_RUN_ID, expires_at)

    conn2 = get_connection()
    clock2 = FixedClock(clock.now())
    ssm2 = SeatStateManager(conn2, clock2)

    mv = reset_state["matrix_version"]
    result_a = ssm.hold(SERVICE_RUN_ID, GOLDEN_SEAT, GOLDEN_SEGMENTS, mv, "idem-a", offer_a)
    assert result_a.status == "ACTIVE"

    with pytest.raises(DomainError) as exc_info:
        ssm2.hold(SERVICE_RUN_ID, GOLDEN_SEAT, GOLDEN_SEGMENTS, mv, "idem-b", offer_b)
    assert exc_info.value.http_status == 409

    seatmap = ssm.get_seatmap(SERVICE_RUN_ID)
    states = seatmap["seats"][GOLDEN_SEAT]
    assert states["3"] == "HELD" and states["4"] == "HELD"
    conn2.close()


def test_no_partial_hold_on_conflict(reset_state, ssm, clock, conn):
    """Segment 3 đã HELD trước bởi hold khác -> hold mới cho [3,4] fail toàn bộ,
    segment 4 KHÔNG bị ghi HELD một phần."""
    offer_a, offer_b = "offer_partial_a", "offer_partial_b"
    expires_at = clock.now() + timedelta(minutes=5)
    insert_test_offer(conn, offer_a, SERVICE_RUN_ID, expires_at)
    insert_test_offer(conn, offer_b, SERVICE_RUN_ID, expires_at)

    mv = reset_state["matrix_version"]
    r1 = ssm.hold(SERVICE_RUN_ID, GOLDEN_SEAT, [3], mv, "idem-partial-a", offer_a)
    with pytest.raises(DomainError):
        ssm.hold(SERVICE_RUN_ID, GOLDEN_SEAT, [3, 4], r1.new_matrix_version, "idem-partial-b", offer_b)

    seatmap = ssm.get_seatmap(SERVICE_RUN_ID)
    assert seatmap["seats"][GOLDEN_SEAT]["4"] == "FREE"


def test_same_idempotency_key_same_result(reset_state, ssm, clock, conn):
    offer_id = "offer_idem"
    expires_at = clock.now() + timedelta(minutes=5)
    insert_test_offer(conn, offer_id, SERVICE_RUN_ID, expires_at)
    mv = reset_state["matrix_version"]

    r1 = ssm.hold(SERVICE_RUN_ID, GOLDEN_SEAT, GOLDEN_SEGMENTS, mv, "idem-same", offer_id)
    r2 = ssm.hold(SERVICE_RUN_ID, GOLDEN_SEAT, GOLDEN_SEGMENTS, mv, "idem-same", offer_id)
    assert r1.hold_id == r2.hold_id


def test_confirm_after_expiry_returns_410(reset_state, ssm, clock, conn):
    offer_id = "offer_expire_confirm"
    expires_at = clock.now() + timedelta(minutes=5)
    insert_test_offer(conn, offer_id, SERVICE_RUN_ID, expires_at)
    mv = reset_state["matrix_version"]

    r = ssm.hold(SERVICE_RUN_ID, GOLDEN_SEAT, GOLDEN_SEGMENTS, mv, "idem-expire-confirm", offer_id)
    clock.advance(700)  # > HOLD_TTL_SECONDS (600s)

    with pytest.raises(HoldExpired):
        ssm.confirm(r.hold_id, "confirm-idem-1")


def test_expiry_releases_all_legs(reset_state, ssm, clock, conn):
    offer_id = "offer_expire_release"
    expires_at = clock.now() + timedelta(minutes=5)
    insert_test_offer(conn, offer_id, SERVICE_RUN_ID, expires_at)
    mv = reset_state["matrix_version"]

    ssm.hold(SERVICE_RUN_ID, GOLDEN_SEAT, GOLDEN_SEGMENTS, mv, "idem-release", offer_id)
    clock.advance(700)
    ssm.expire_due_holds(SERVICE_RUN_ID)

    seatmap = ssm.get_seatmap(SERVICE_RUN_ID)
    states = seatmap["seats"][GOLDEN_SEAT]
    assert states["3"] == "FREE" and states["4"] == "FREE"


def test_price_and_seat_plan_unchanged_offer_to_confirm(reset_state, ssm, clock, conn):
    offer_id = "offer_price_lock"
    expires_at = clock.now() + timedelta(minutes=5)
    insert_test_offer(conn, offer_id, SERVICE_RUN_ID, expires_at, final_price_vnd=285000)
    mv = reset_state["matrix_version"]

    r = ssm.hold(SERVICE_RUN_ID, GOLDEN_SEAT, GOLDEN_SEGMENTS, mv, "idem-price-lock", offer_id)
    confirm_result = ssm.confirm(r.hold_id, "confirm-price-lock")
    assert confirm_result.final_price_vnd == 285000
    assert confirm_result.status == "CONFIRMED"

    # idempotent replay — cùng kết quả, không tạo booking thứ 2
    confirm_result2 = ssm.confirm(r.hold_id, "confirm-price-lock-2")
    assert confirm_result2.booking_id == confirm_result.booking_id


def test_invalid_scenario_reset_does_not_mutate_state(ssm, conn, tmp_path):
    """Seed thư mục hỏng (thiếu file) -> reset raise, state cũ giữ nguyên."""
    ssm.reset_scenario(_seed_dir())  # baseline thật trước
    before = ssm.get_seatmap(SERVICE_RUN_ID)

    bad_dir = tmp_path / "bad_seed"
    bad_dir.mkdir()
    (bad_dir / "scenario.json").write_text('{"service_run_id":"X"}', encoding="utf-8")
    with pytest.raises(Exception):
        ssm.reset_scenario(bad_dir)

    after = ssm.get_seatmap(SERVICE_RUN_ID)
    assert before == after


def test_reset_deterministic_same_checksum(ssm):
    r1 = ssm.reset_scenario(_seed_dir())
    r2 = ssm.reset_scenario(_seed_dir())
    assert r1["checksum"] == r2["checksum"]


def test_stale_matrix_version_returns_409(reset_state, ssm, clock, conn):
    offer_id = "offer_stale"
    expires_at = clock.now() + timedelta(minutes=5)
    insert_test_offer(conn, offer_id, SERVICE_RUN_ID, expires_at)
    stale_mv = reset_state["matrix_version"] - 1 if reset_state["matrix_version"] > 0 else 999
    with pytest.raises(StaleSnapshot) as exc_info:
        ssm.hold(SERVICE_RUN_ID, GOLDEN_SEAT, GOLDEN_SEGMENTS, stale_mv, "idem-stale", offer_id)
    assert exc_info.value.http_status == 409


def _seed_dir():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "seed"

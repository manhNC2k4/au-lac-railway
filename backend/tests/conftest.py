# -*- coding: utf-8 -*-
"""Fixture chung: reset scenario thật trên Postgres trước mỗi test cần state.
Yêu cầu: docker compose up -d db flyway  (DATABASE_URL mặc định trỏ localhost:5432)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.state.clock import FixedClock
from src.state.db import get_connection
from src.state.seat_state_manager import SeatStateManager

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
SERVICE_RUN_ID = "SE1_2026-06-15_LE"


@pytest.fixture
def clock():
    return FixedClock(datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc))


@pytest.fixture
def conn():
    c = get_connection()
    yield c
    c.rollback()
    c.close()


@pytest.fixture
def ssm(conn, clock):
    return SeatStateManager(conn, clock)


@pytest.fixture
def reset_state(ssm):
    """Reset golden scenario thật trước test — dùng connection riêng để commit
    thấy được bởi các connection khác (hold test dùng 2 SeatStateManager song song)."""
    result = ssm.reset_scenario(SEED_DIR)
    return result


def insert_test_offer(conn, offer_id: str, service_run_id: str, expires_at, decision="ACCEPT",
                       matrix_version=1, forecast_version=1, policy_version=1, final_price_vnd=300000,
                       seat_plan="[]"):
    """Test helper — seat_hold.offer_id có FK tới offer, nên test CAS cần 1 dòng offer hợp lệ.
    `seat_plan` nhận JSON string sẵn (mặc định rỗng) — test P5 truyền plan >=2 leg để dựng
    tình huống ghép nhiều ghế mà không cần chạy full resolver/seatmap."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO offer (offer_id, service_run_id, matrix_version, forecast_version, policy_version,
                                   decision, seat_plan, final_price_vnd, expires_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (offer_id, service_run_id, matrix_version, forecast_version, policy_version,
             decision, seat_plan, final_price_vnd, expires_at),
        )
    conn.commit()

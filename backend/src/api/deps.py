# -*- coding: utf-8 -*-
"""Shared request-scoped deps: DB connection + Clock + SeatStateManager."""
from pathlib import Path

from ..state.clock import Clock
from ..state.db import get_connection
from ..state.seat_state_manager import SeatStateManager

SEED_DIR = Path(__file__).resolve().parent.parent.parent / "seed"
_clock = Clock()


def get_clock() -> Clock:
    return _clock


def set_clock(clock: Clock) -> None:
    """Test hook — swap in a FixedClock."""
    global _clock
    _clock = clock


def get_state_manager() -> SeatStateManager:
    conn = get_connection()
    return SeatStateManager(conn, _clock)

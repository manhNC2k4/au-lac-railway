# -*- coding: utf-8 -*-
"""Shared request-scoped deps: DB connection + Clock + SeatStateManager +
P2/P3/P4 model artifacts (Pricer/DemandModel, live-import từ `app/`, nạp 1 lần lúc boot)."""
import logging
import sys
from pathlib import Path

from ..state.clock import Clock
from ..state.db import get_connection
from ..state.errors import PolicyUnavailable
from ..state.seat_state_manager import SeatStateManager

SEED_DIR = Path(__file__).resolve().parent.parent.parent / "seed"
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:          # `app/` package sống ở repo root, ngoài backend/
    sys.path.insert(0, str(REPO_ROOT))

_clock = Clock()
_logger = logging.getLogger(__name__)

# fail-closed: artifact thiếu/load lỗi lúc boot -> None -> endpoint dùng đến trả 503
# POLICY_UNAVAILABLE (get_pricer/get_demand_model), KHÔNG rơi về công thức mặc định
_pricer = None
_demand_model = None


def load_models() -> None:
    """Nạp Pricer + DemandModel từ `models/artifacts/` 1 lần lúc app start (BACKEND_GUIDE.md §2).
    KHÔNG raise — lỗi load bị nuốt + log, để app vẫn boot; endpoint pricing/bid tự phát 503."""
    global _pricer, _demand_model
    from app.bt1_forecast import DemandModel
    from app.bt5_pricing import Pricer
    try:
        _pricer = Pricer.load(use_elasticity=True)
    except Exception:
        _logger.exception("load_models: Pricer.load thất bại — pricing sẽ trả 503")
        _pricer = None
    try:
        _demand_model = DemandModel.load()
    except Exception:
        _logger.exception("load_models: DemandModel.load thất bại — forecast sẽ trả 503")
        _demand_model = None


def get_pricer():
    if _pricer is None:
        raise PolicyUnavailable("Pricer chưa nạp được (artifact thiếu/lỗi) — fail closed 503", {})
    return _pricer


def get_demand_model():
    if _demand_model is None:
        raise PolicyUnavailable("DemandModel chưa nạp được (artifact thiếu/lỗi) — fail closed 503", {})
    return _demand_model


def get_clock() -> Clock:
    return _clock


def set_clock(clock: Clock) -> None:
    """Test hook — swap in a FixedClock."""
    global _clock
    _clock = clock


def get_state_manager() -> SeatStateManager:
    conn = get_connection()
    return SeatStateManager(conn, _clock)

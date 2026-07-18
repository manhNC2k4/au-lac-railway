# -*- coding: utf-8 -*-
"""P2/P3/P4-Bước3 · boot sequence nạp Pricer/DemandModel (live-import app/) — fail-closed 503."""
from unittest.mock import patch

import pytest

from src.api import deps
from src.state.errors import PolicyUnavailable


@pytest.fixture(autouse=True)
def _restore_state():
    """Mỗi test độc lập, không rò global _pricer/_demand_model sang test khác."""
    prev_pricer, prev_demand = deps._pricer, deps._demand_model
    yield
    deps._pricer, deps._demand_model = prev_pricer, prev_demand


def test_load_models_success_loads_real_artifacts():
    deps.load_models()
    assert deps._pricer is not None
    assert deps._demand_model is not None
    assert deps.get_pricer() is deps._pricer
    assert deps.get_demand_model() is deps._demand_model


def test_get_pricer_fails_closed_when_artifact_missing():
    deps._pricer = None
    with pytest.raises(PolicyUnavailable) as exc:
        deps.get_pricer()
    assert exc.value.http_status == 503
    assert exc.value.error_code == "POLICY_UNAVAILABLE"


def test_get_demand_model_fails_closed_when_artifact_missing():
    deps._demand_model = None
    with pytest.raises(PolicyUnavailable) as exc:
        deps.get_demand_model()
    assert exc.value.http_status == 503


def test_load_models_swallows_pricer_load_error_and_stays_fail_closed():
    with patch("app.bt5_pricing.Pricer.load", side_effect=FileNotFoundError("no artifact")):
        deps.load_models()
    assert deps._pricer is None
    with pytest.raises(PolicyUnavailable):
        deps.get_pricer()


def test_load_models_swallows_demand_model_load_error_and_stays_fail_closed():
    with patch("app.bt1_forecast.DemandModel.load", side_effect=FileNotFoundError("no artifact")):
        deps.load_models()
    assert deps._demand_model is None
    with pytest.raises(PolicyUnavailable):
        deps.get_demand_model()

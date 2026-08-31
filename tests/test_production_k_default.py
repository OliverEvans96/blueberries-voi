"""Production freshness grid resolution K defaults to 30."""

from __future__ import annotations

from blueberries_voi.controller.session_loop import default_session_config
from blueberries_voi.experiments.filter_accuracy import session_config_base
from blueberries_voi.experiments.voi_profit import profit_session_config
from blueberries_voi.filter.constants import PRODUCTION_K
from blueberries_voi.simulator.session import EngineSession


def test_production_k_constant() -> None:
    assert PRODUCTION_K == 30


def test_profit_session_config_k() -> None:
    assert profit_session_config()["K"] == 30


def test_filter_accuracy_session_config_k() -> None:
    assert session_config_base()["K"] == 30


def test_default_session_config_k() -> None:
    assert default_session_config()["K"] == 30


def test_engine_session_python_default_k() -> None:
    session = EngineSession()
    assert session._K == 30

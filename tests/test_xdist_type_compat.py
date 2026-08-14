"""Regression: EpisodeLog / OrderSchedule identity under dual module paths."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from blueberries_voi._type_compat import is_same_package_type
from blueberries_voi.sim.order_schedule import OrderSchedule
from blueberries_voi.sim.types_log import EpisodeLog

_SIM = Path(__file__).resolve().parents[1] / "src" / "blueberries_voi" / "sim"


def _load_as(module_name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Dataclasses with from __future__ import annotations look up the module
    # in sys.modules while the class body is processed.
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(module_name, None)
    return mod


def test_episodelog_isinstance_fails_under_src_dual_import() -> None:
    """Documents the xdist flake: src.* vs blueberries_voi.* are distinct types."""
    twin_mod = _load_as(
        "src.blueberries_voi.sim.types_log",
        _SIM / "types_log.py",
    )
    ep = twin_mod.EpisodeLog(n_burn=2, n_score=3)
    assert not isinstance(ep, EpisodeLog)
    assert is_same_package_type(ep, EpisodeLog)
    assert ep.n_burn == 2
    assert len(ep.scored) == 0


def test_orderschedule_isinstance_fails_under_src_dual_import() -> None:
    twin_mod = _load_as(
        "src.blueberries_voi.sim.order_schedule",
        _SIM / "order_schedule.py",
    )
    schedule = twin_mod.OrderSchedule()
    assert not isinstance(schedule, OrderSchedule)
    assert is_same_package_type(schedule, OrderSchedule)
    assert set(schedule.order_weekdays) == set(OrderSchedule().order_weekdays)


def test_is_same_package_type_rejects_unrelated_classes() -> None:
    assert is_same_package_type(EpisodeLog(), EpisodeLog)
    assert not is_same_package_type(EpisodeLog(), OrderSchedule)

"""T-110: EngineSession dispatches to PyO3 when BLUEBERRIES_VOI_BACKEND=rust."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import numpy as np

from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator.belief import empty_flat_belief
from blueberries_voi.simulator.session import EngineSession

if TYPE_CHECKING:
    import pytest

_FLAT = empty_flat_belief(L=2, K=4)


def _ships() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T110",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]


def _cfg() -> dict[str, Any]:
    return {
        "shipments": _ships(),
        "n_particles": 8,
        "H": 2,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": True,
    }


def _snap(*, seq: int = 0, day: int = 0) -> dict[str, Any]:
    return {
        "seq": seq,
        "episode_day": day,
        "belief": dict(_FLAT),
        "applied_config": {},
        "history": [],
        "live_lots": [],
        "pipeline": [],
    }


def _delta(*, seq: int = 1, day: int = 0, order: int = 0) -> dict[str, Any]:
    return {
        "seq": seq,
        "episode_day": day,
        "day": {
            "day": day,
            "order_qty": order,
            "arrivals": 0,
            "sales_total": 0,
            "waste_total": 0,
            "demand": 0,
            "L": 0,
        },
        "live_lots": [],
        "pipeline": [],
        "drop_oldest": False,
        "belief": dict(_FLAT),
    }


class _FakePyEngineSession:
    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)
        self.crossings = 0
        self.inits = 0
        self.steps: list[int] = []
        self.step_n_calls = 0
        self.acts = 0

    def init(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.inits += 1
        self.crossings += 1
        return _snap()

    def reset(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.init(*args, **kwargs)

    def step(self, order_qty: int) -> dict[str, Any]:
        self.steps.append(int(order_qty))
        self.crossings += 1
        return _delta(order=int(order_qty))

    def step_n(self, orders: list[int]) -> list[dict[str, Any]]:
        self.step_n_calls += 1
        self.crossings += 1
        return [_delta(seq=i + 1, order=int(q)) for i, q in enumerate(orders)]

    def act(self, policy: str | None = None, **kwargs: Any) -> dict[str, Any]:
        self.acts += 1
        self.crossings += 1
        return _delta()

    def host_crossings(self) -> int:
        return int(self.crossings)


def _install_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, _FakePyEngineSession]:
    holder: dict[str, _FakePyEngineSession] = {}

    def factory(seed: int = 0) -> _FakePyEngineSession:
        sess = _FakePyEngineSession(seed)
        holder["s"] = sess
        return sess

    fake = SimpleNamespace(PyEngineSession=factory)
    monkeypatch.setattr("blueberries_voi.backend.rust_available", lambda: True)
    monkeypatch.setattr("blueberries_voi.backend.rust_core", fake)
    return holder


def test_rust_init_step_reset_act(monkeypatch: pytest.MonkeyPatch) -> None:
    holder = _install_fake(monkeypatch)
    session = EngineSession()
    snap = session.init(_cfg(), seed=3)
    assert snap["seq"] == 0
    assert "belief" in snap
    inner = holder["s"]
    assert inner.inits == 1
    delta = session.step(8)
    assert delta["seq"] == 1
    assert "day" in delta
    assert inner.steps == [8]
    session.reset(seed=3)
    assert inner.inits >= 2
    session.act(policy="rollout")
    assert inner.acts == 1


def test_rust_step_n_is_one_ffi_crossing(monkeypatch: pytest.MonkeyPatch) -> None:
    holder = _install_fake(monkeypatch)
    session = EngineSession()
    session.init(_cfg(), seed=1)
    inner = holder["s"]
    before = inner.host_crossings()
    orders = [0, 8, 0, 8, 0, 8, 0]
    deltas = session.step_n(orders)
    assert len(deltas) == 7
    assert inner.step_n_calls == 1
    assert inner.host_crossings() == before + 1
    assert session.host_crossings() == inner.host_crossings()


def test_python_skips_pyo3(monkeypatch: pytest.MonkeyPatch) -> None:
    import pytest as pt

    monkeypatch.setattr("blueberries_voi.backend.rust_available", lambda: False)
    monkeypatch.setattr("blueberries_voi.backend.rust_core", None)
    session = EngineSession()
    with pt.raises(RuntimeError, match="T-121 Wave F"):
        session.init(_cfg(), seed=1)

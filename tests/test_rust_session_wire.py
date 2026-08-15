"""T-121a (Wave A): PyO3 wire fidelity — RED before A1/A2/A3 implement.

With ``BLUEBERRIES_VOI_BACKEND=rust``, EngineSession must receive full Snapshot /
DayDelta payloads from ``blueberries_voi._core`` (not stub empty belief / missing
schedule+demand_summary). Skips entire module when the extension is absent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator.session import EngineSession, demand_summary_wire, schedule_wire

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

rust_core = _maybe_core

_FLAT_BELIEF_KEYS = frozenset({"lot_counts", "age_marginals", "tau_grid", "L", "K"})
_SCHEDULE_KEYS = frozenset({"delivery_weekdays", "order_weekdays", "lead_time_days", "epoch"})
_DEMAND_SUMMARY_KEYS = frozenset({"scale_mu", "dow_means"})


@pytest.fixture(autouse=True)
def _rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")


def _ships() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T121a",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]


def _cfg(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "shipments": _ships(),
        "n_particles": 32,
        "H": 3,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
    }
    cfg.update(overrides)
    return cfg


def _pyo3_init_raw(*, seed: int = 42) -> Mapping[str, Any]:
    sess = rust_core.PyEngineSession(seed)
    times = [[0.0, 1.0, 2.0]]
    temps = [[1.0, 1.0, 1.0]]
    raw = sess.init(seed, 1, True, 3, 1, 1, times, temps, 32)
    assert isinstance(raw, Mapping), "PyEngineSession.init must return a mapping"
    return raw


def _assert_belief_populated(belief: Any, *, l_dim: int, k_dim: int, label: str) -> None:
    assert isinstance(belief, Mapping), f"{label}.belief must be a mapping"
    missing = _FLAT_BELIEF_KEYS - set(belief)
    assert not missing, f"{label}.belief missing flat fields {sorted(missing)}"
    assert int(belief["L"]) == l_dim, (
        f"{label}.belief.L must match config L={l_dim}, got {belief['L']!r}"
    )
    assert int(belief["K"]) == k_dim, (
        f"{label}.belief.K must match config K={k_dim}, got {belief['K']!r}"
    )
    lot_counts = list(belief["lot_counts"])
    age_marginals = list(belief["age_marginals"])
    tau_grid = list(belief["tau_grid"])
    assert len(lot_counts) == l_dim, (
        f"{label}.belief.lot_counts length {len(lot_counts)} != L={l_dim}"
    )
    assert len(age_marginals) == l_dim * k_dim
    assert len(tau_grid) == k_dim
    assert any(float(x) != 0.0 for x in lot_counts), (
        f"{label}.belief.lot_counts must be non-empty (filter bank wired), got {lot_counts!r}"
    )
    assert any(float(x) != 0.0 for x in age_marginals), (
        f"{label}.belief.age_marginals must be non-empty, got stub zeros"
    )


def _assert_schedule_populated(schedule: Any, *, label: str) -> None:
    assert isinstance(schedule, Mapping), f"{label}.schedule must be a mapping"
    missing = _SCHEDULE_KEYS - set(schedule)
    assert not missing, f"{label}.schedule missing keys {sorted(missing)}"
    delivery = schedule["delivery_weekdays"]
    order = schedule["order_weekdays"]
    assert isinstance(delivery, Sequence) and not isinstance(delivery, (str, bytes))
    assert isinstance(order, Sequence) and not isinstance(order, (str, bytes))
    assert len(delivery) > 0 and len(order) > 0, (
        f"{label}.schedule weekday lists must be non-empty"
    )


def _assert_demand_summary_populated(summary: Any, *, label: str) -> None:
    assert isinstance(summary, Mapping), f"{label}.demand_summary must be a mapping"
    missing = _DEMAND_SUMMARY_KEYS - set(summary)
    assert not missing, f"{label}.demand_summary missing keys {sorted(missing)}"
    assert float(summary["scale_mu"]) > 0.0
    dow = summary["dow_means"]
    assert isinstance(dow, Sequence) and not isinstance(dow, (str, bytes))
    assert len(dow) == 7, f"{label}.demand_summary.dow_means must have length 7"
    assert any(float(x) > 0.0 for x in dow), (
        f"{label}.demand_summary.dow_means must be non-empty"
    )


def _assert_live_lots_populated(live_lots: Any, *, label: str) -> None:
    assert isinstance(live_lots, list), f"{label}.live_lots must be a list"
    assert len(live_lots) > 0, (
        f"{label}.live_lots must be non-empty after inventory arrives (not stub [])"
    )
    first = live_lots[0]
    assert isinstance(first, Mapping), f"{label}.live_lots[0] must be a lot mapping"
    for key in ("lot_id", "n", "tau"):
        assert key in first, f"{label}.live_lots[0] missing {key!r}"


# --- EngineSession + rust backend (A1 integration) ---


def test_rust_init_snapshot_belief_lot_counts_nonempty() -> None:
    session = EngineSession()
    snap = session.init(_cfg(), seed=42)
    _assert_belief_populated(snap["belief"], l_dim=2, k_dim=4, label="init Snapshot")


def test_rust_init_snapshot_schedule_nonempty() -> None:
    session = EngineSession()
    snap = session.init(_cfg(), seed=42)
    _assert_schedule_populated(snap["schedule"], label="init Snapshot")
    expected = schedule_wire()
    assert snap["schedule"]["epoch"] == expected["epoch"]


def test_rust_init_snapshot_demand_summary_nonempty() -> None:
    session = EngineSession()
    snap = session.init(_cfg(), seed=42)
    _assert_demand_summary_populated(snap["demand_summary"], label="init Snapshot")
    expected = demand_summary_wire()
    assert float(snap["demand_summary"]["scale_mu"]) == pytest.approx(
        float(expected["scale_mu"])
    )


def test_rust_init_snapshot_live_lots_key_present() -> None:
    """Day-0 inventory may be empty; wire must still expose the live_lots list."""
    session = EngineSession()
    snap = session.init(_cfg(), seed=42)
    assert isinstance(snap["live_lots"], list)


def test_rust_step_delta_belief_nonempty() -> None:
    session = EngineSession()
    session.init(_cfg(), seed=42)
    delta = session.step(8)
    _assert_belief_populated(delta["belief"], l_dim=2, k_dim=4, label="DayDelta")


def test_rust_step_delta_live_lots_nonempty_after_arrival() -> None:
    """After lead_time, an order must surface lots on the wire (seed 42, order 8).

    MWF schedule: day 0 is Monday (not an order day). step(8) on day 1 (Tuesday)
    places the order; lead_time=1 → arrival on day 2; step(0) observes live_lots.
    """
    session = EngineSession()
    session.init(_cfg(), seed=42)
    session.step(8)
    session.step(8)
    delta = session.step(0)
    _assert_belief_populated(delta["belief"], l_dim=2, k_dim=4, label="DayDelta")
    _assert_live_lots_populated(delta["live_lots"], label="DayDelta")


def test_rust_step_delta_seq_is_session_counter_not_episode_day() -> None:
    session = EngineSession()
    session.init(_cfg(), seed=7)
    first = session.step(0)
    second = session.step(0)
    assert first["seq"] == 1
    assert second["seq"] == 2
    assert first["seq"] != first["episode_day"], (
        "DayDelta.seq must be monotonic session counter, not episode_day alias"
    )


# --- PyO3 native wire (A1: no Python _coerce_snapshot backfill) ---


def test_pyo3_init_includes_schedule_and_demand_summary() -> None:
    raw = _pyo3_init_raw()
    assert "schedule" in raw, "PyO3 init must include schedule (delegate snapshot_value)"
    assert "demand_summary" in raw, (
        "PyO3 init must include demand_summary (delegate snapshot_value)"
    )
    _assert_schedule_populated(raw["schedule"], label="PyO3 init")
    _assert_demand_summary_populated(raw["demand_summary"], label="PyO3 init")


def test_pyo3_init_belief_delegates_to_session_bank() -> None:
    raw = _pyo3_init_raw()
    _assert_belief_populated(raw["belief"], l_dim=2, k_dim=4, label="PyO3 init")


def test_pyo3_step_delta_live_lots_nonempty_after_arrival() -> None:
    sess = rust_core.PyEngineSession(42)
    times = [[0.0, 1.0, 2.0]]
    temps = [[1.0, 1.0, 1.0]]
    sess.init(42, 1, True, 3, 1, 1, times, temps, 32)
    sess.step(8)  # day 0 Mon — no order day
    sess.step(8)  # day 1 Tue — order 8, arrival day 2
    delta = sess.step(0)
    assert isinstance(delta, Mapping)
    _assert_belief_populated(delta["belief"], l_dim=2, k_dim=4, label="PyO3 DayDelta")
    _assert_live_lots_populated(delta["live_lots"], label="PyO3 DayDelta")

"""T-121a / T-C2-A session wire: PyO3 f-native belief fidelity (RED).

With ``BLUEBERRIES_VOI_BACKEND=rust``, EngineSession must receive full Snapshot /
DayDelta payloads from ``blueberries_voi._core`` with ``f_grid`` / ``f_marginals``
(not legacy ``tau_grid`` / ``age_marginals``). Skips runtime tests when the
extension is absent; source guards always run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator.session import (
    EngineSession,
    demand_summary_wire,
    schedule_wire,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SESSION_RS = _REPO_ROOT / "crates" / "voi_core" / "src" / "session.rs"
_VOI_RS = _REPO_ROOT / "crates" / "voi_core" / "src" / "voi.rs"

rust_core = _maybe_core
_RUST_RUNTIME = pytest.mark.skipif(
    _maybe_core is None,
    reason="blueberries_voi._core not built",
)

_FLAT_BELIEF_KEYS = frozenset({"lot_counts", "f_marginals", "f_grid", "L", "K"})
_LEGACY_BELIEF_KEYS = frozenset({"age_marginals", "tau_grid"})
_SCHEDULE_KEYS = frozenset(
    {"delivery_weekdays", "order_weekdays", "lead_time_days", "epoch"}
)
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
    assert rust_core is not None
    sess = rust_core.PyEngineSession(seed)
    times = [[0.0, 1.0, 2.0]]
    temps = [[1.0, 1.0, 1.0]]
    raw = sess.init(seed, 1, True, 3, 1, 1, times, temps, 32)
    assert isinstance(raw, Mapping), "PyEngineSession.init must return a mapping"
    return raw


def _assert_belief_populated(
    belief: Any,
    *,
    l_dim: int,
    k_dim: int,
    label: str,
    require_lot_mass: bool = True,
) -> None:
    assert isinstance(belief, Mapping), f"{label}.belief must be a mapping"
    missing = _FLAT_BELIEF_KEYS - set(belief)
    assert not missing, f"{label}.belief missing flat fields {sorted(missing)}"
    legacy = _LEGACY_BELIEF_KEYS & set(belief)
    assert not legacy, (
        f"{label}.belief must not expose legacy τ-wire keys {sorted(legacy)} "
        f"(T-C2-A f-native wire)"
    )
    assert int(belief["L"]) == l_dim, (
        f"{label}.belief.L must match config L={l_dim}, got {belief['L']!r}"
    )
    assert int(belief["K"]) == k_dim, (
        f"{label}.belief.K must match config K={k_dim}, got {belief['K']!r}"
    )
    lot_counts = list(belief["lot_counts"])
    f_marginals = list(belief["f_marginals"])
    f_grid = list(belief["f_grid"])
    assert len(lot_counts) == l_dim, (
        f"{label}.belief.lot_counts length {len(lot_counts)} != L={l_dim}"
    )
    assert len(f_marginals) == l_dim * k_dim, (
        f"{label}.belief.f_marginals length {len(f_marginals)} != L*K={l_dim * k_dim}"
    )
    assert len(f_grid) == k_dim, (
        f"{label}.belief.f_grid length {len(f_grid)} != K={k_dim}"
    )
    for i, f_val in enumerate(f_grid):
        fv = float(f_val)
        assert 0.0 <= fv <= 1.0, (
            f"{label}.belief.f_grid[{i}]={fv} outside freshness [0, 1]"
        )
    if require_lot_mass:
        assert any(float(x) != 0.0 for x in lot_counts), (
            f"{label}.belief.lot_counts must be non-empty "
            f"(filter bank wired), got {lot_counts!r}"
        )
    else:
        assert sum(float(x) for x in lot_counts) == pytest.approx(0.0), (
            f"{label}.belief.lot_counts must be zero at empty shelf, got {lot_counts!r}"
        )
    assert any(float(x) != 0.0 for x in f_marginals), (
        f"{label}.belief.f_marginals must be non-empty, got stub zeros"
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
    for key in ("lot_id", "n", "mean_f"):
        assert key in first, f"{label}.live_lots[0] missing {key!r}"


# --- EngineSession + rust backend (A1 integration) ---


@_RUST_RUNTIME
def test_rust_init_snapshot_belief_zero_lot_counts() -> None:
    session = EngineSession()
    snap = session.init(_cfg(), seed=42)
    _assert_belief_populated(
        snap["belief"],
        l_dim=2,
        k_dim=4,
        label="init Snapshot",
        require_lot_mass=False,
    )


@_RUST_RUNTIME
def test_rust_init_snapshot_schedule_nonempty() -> None:
    session = EngineSession()
    snap = session.init(_cfg(), seed=42)
    _assert_schedule_populated(snap["schedule"], label="init Snapshot")
    expected = schedule_wire()
    assert snap["schedule"]["epoch"] == expected["epoch"]


@_RUST_RUNTIME
def test_rust_init_snapshot_demand_summary_nonempty() -> None:
    session = EngineSession()
    snap = session.init(_cfg(), seed=42)
    _assert_demand_summary_populated(snap["demand_summary"], label="init Snapshot")
    expected = demand_summary_wire()
    assert float(snap["demand_summary"]["scale_mu"]) == pytest.approx(
        float(expected["scale_mu"])
    )


@_RUST_RUNTIME
def test_rust_init_snapshot_live_lots_key_present() -> None:
    """Day-0 inventory may be empty; wire must still expose the live_lots list."""
    session = EngineSession()
    snap = session.init(_cfg(), seed=42)
    assert isinstance(snap["live_lots"], list)


@_RUST_RUNTIME
def test_rust_step_delta_belief_nonempty_after_arrival() -> None:
    session = EngineSession()
    session.init(_cfg(), seed=42)
    session.step(0)
    session.step(8)
    delta = session.step(0)
    _assert_belief_populated(delta["belief"], l_dim=2, k_dim=4, label="DayDelta")


@_RUST_RUNTIME
def test_rust_step_delta_live_lots_nonempty_after_arrival() -> None:
    """After lead_time, an order must surface lots on the wire (seed 42, order 8).

    Day 0 (Mon) is not an order day; advance once, order on Tue (day 1), arrive
    after lead_time on day 2.
    """
    session = EngineSession()
    session.init(_cfg(), seed=42)
    session.step(0)
    session.step(8)
    delta = session.step(0)
    _assert_belief_populated(delta["belief"], l_dim=2, k_dim=4, label="DayDelta")
    _assert_live_lots_populated(delta["live_lots"], label="DayDelta")


@_RUST_RUNTIME
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


@_RUST_RUNTIME
def test_pyo3_init_includes_schedule_and_demand_summary() -> None:
    raw = _pyo3_init_raw()
    assert "schedule" in raw, (
        "PyO3 init must include schedule (delegate snapshot_value)"
    )
    assert "demand_summary" in raw, (
        "PyO3 init must include demand_summary (delegate snapshot_value)"
    )
    _assert_schedule_populated(raw["schedule"], label="PyO3 init")
    _assert_demand_summary_populated(raw["demand_summary"], label="PyO3 init")


@_RUST_RUNTIME
def test_pyo3_init_belief_delegates_to_session_bank() -> None:
    raw = _pyo3_init_raw()
    _assert_belief_populated(
        raw["belief"],
        l_dim=2,
        k_dim=4,
        label="PyO3 init",
        require_lot_mass=False,
    )


@_RUST_RUNTIME
def test_pyo3_step_delta_live_lots_nonempty_after_arrival() -> None:
    assert rust_core is not None
    sess = rust_core.PyEngineSession(42)
    times = [[0.0, 1.0, 2.0]]
    temps = [[1.0, 1.0, 1.0]]
    sess.init(42, 1, True, 3, 1, 1, times, temps, 32)
    sess.step(0)
    sess.step(8)
    delta = sess.step(0)
    assert isinstance(delta, Mapping)
    _assert_belief_populated(delta["belief"], l_dim=2, k_dim=4, label="PyO3 DayDelta")
    _assert_live_lots_populated(delta["live_lots"], label="PyO3 DayDelta")


# --- T-C2-A AC-session / AC-guards: f-native production hot path ---


def _rust_source_before_tests(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "#[cfg(test)]"
    idx = text.find(marker)
    return text if idx < 0 else text[:idx]


def test_voi_core_session_production_uses_filter_step_unit() -> None:
    """AC-session: advance_one must call unit_pf::filter_step_unit, not counts+τ PF."""
    text = _rust_source_before_tests(_SESSION_RS)
    assert "filter_step_unit" in text, (
        "session.rs production path must call filter_step_unit (T-C2-A AC-session)"
    )
    assert "UnitParticleBank" in text, (
        "session.rs production path must use UnitParticleBank (T-C2-A AC-session)"
    )
    assert "particle_filter::filter_step" not in text, (
        "session.rs production path must not call legacy particle_filter::filter_step"
    )


def test_voi_core_voi_production_uses_filter_step_unit() -> None:
    """AC-session: run_voi_crn_cell must score via unit_pf, not filter_step."""
    text = _rust_source_before_tests(_VOI_RS)
    assert "filter_step_unit" in text, (
        "voi.rs production path must call filter_step_unit (T-C2-A AC-session)"
    )
    assert "UnitParticleBank" in text, (
        "voi.rs production path must use UnitParticleBank (T-C2-A AC-session)"
    )
    assert "filter_step(&" not in text, (
        "voi.rs production path must not call legacy filter_step on ParticleBank"
    )


def test_voi_core_session_belief_export_uses_f_native_wire() -> None:
    """AC-belief / AC-python-wire: Snapshot belief uses f_grid / f_marginals keys."""
    text = _rust_source_before_tests(_SESSION_RS)
    assert "belief_flat_from_unit_bank" in text, (
        "session.rs must export belief via belief_flat_from_unit_bank"
    )
    assert '"f_grid"' in text and '"f_marginals"' in text, (
        "session.rs belief export must wire f_grid and f_marginals"
    )
    assert '"tau_grid"' not in text and '"age_marginals"' not in text, (
        "session.rs production belief export must not emit legacy τ-wire keys"
    )


def test_voi_core_session_configure_accepts_units_per_lot() -> None:
    """AC-session: configure exposes units_per_lot (default 15)."""
    text = _SESSION_RS.read_text(encoding="utf-8")
    assert "units_per_lot" in text, (
        "EngineSession::configure must accept units_per_lot (T-C2-A AC-session)"
    )


def test_voi_core_session_tests_use_f_marginals_not_age_marginals() -> None:
    """AC-guards: supersede ADR 0105/0106 τ-wire keys in session.rs tests."""
    text = _SESSION_RS.read_text(encoding="utf-8")
    test_block = text.split("#[cfg(test)]", 1)[-1]
    assert '"f_marginals"' in test_block or "f_marginals" in test_block, (
        "session.rs #[cfg(test)] must assert on f_marginals after T-C2-A supersession"
    )
    assert "age_marginals" not in test_block, (
        "session.rs tests must not reference legacy age_marginals (T-C2-A AC-guards)"
    )


@_RUST_RUNTIME
def test_rust_set_obs_scenario_f2_vs_p1_f_marginals_differ_live_lots_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-session: F2 vs P1 differ in f_marginals; live_lots identical."""
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    orders = [8, 0, 8, 0, 8, 0, 8, 0]

    f2 = EngineSession()
    f2.init(_cfg(), seed=11)
    f2.set_obs_scenario("F2")
    f2_last: Mapping[str, Any] | None = None
    for qty in orders:
        f2_last = f2.step(qty)

    p1 = EngineSession()
    p1.init(_cfg(), seed=11)
    p1.set_obs_scenario("P1")
    p1_last: Mapping[str, Any] | None = None
    for qty in orders:
        p1_last = p1.step(qty)

    assert f2_last is not None and p1_last is not None

    b_f2 = f2_last["belief"]
    b_p1 = p1_last["belief"]
    _assert_belief_populated(b_f2, l_dim=2, k_dim=4, label="F2 DayDelta")
    _assert_belief_populated(b_p1, l_dim=2, k_dim=4, label="P1 DayDelta")
    assert list(b_f2["f_marginals"]) != list(b_p1["f_marginals"]), (
        "F2 vs P1 must differ in belief.f_marginals under unit-PF routing"
    )
    assert f2_last["live_lots"] == p1_last["live_lots"], (
        "F2 vs P1 must share identical live_lots (physics CRN parity)"
    )

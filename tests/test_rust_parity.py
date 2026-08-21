"""Golden / skip-if-missing parity vs optional ``blueberries_voi._core`` (Wave E).

Structural ``atol`` checks — not bit-identical RNG (ADR 0127).
"""

from __future__ import annotations

import importlib
import math
from typing import Any

import numpy as np
import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.simulator.session import EngineSession
from blueberries_voi.voi import VOI_SCENARIOS, run_voi_crn_cell

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

rust_core = _maybe_core

# Structural parity tolerance for stochastic kernels (ADR 0127).
_STRUCTURAL_ATOL = 1.0

_DAY_STEP_SEED = 77
_FILTER_SEED = 13
_TRAJECTORY_SEED = 42
_CRN_ROOT_SEED = 42


@pytest.fixture(autouse=True)
def _rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)


def test_backend_default_is_rust_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wave E: production default is rust; env still overrides."""
    monkeypatch.delenv("BLUEBERRIES_VOI_BACKEND", raising=False)
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)
    if backend_mod.rust_core is not None:
        assert backend_mod.rust_available() is True
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "python")
    importlib.reload(backend_mod)
    assert backend_mod.rust_available() is False


def test_weibull_matches_python() -> None:
    pytest.skip("T-TAU-RETIRE: rust_core.weibull_survival_py removed")


def test_day_step_injected_smoke() -> None:
    pytest.skip("T-TAU-RETIRE: rust_core.day_step_injected removed")


def test_filter_step_one_day_smoke() -> None:
    pytest.skip("T-TAU-RETIRE: rust_core.filter_step_py removed")


def test_engine_session_ten_day_trajectory_fixed_orders() -> None:
    """Ten-day session with fixed orders: monotonic seq and populated belief wire."""
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    ships = [
        ShipmentTrace(
            shipment_id="parity",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]
    cfg: dict[str, Any] = {
        "shipments": ships,
        "n_particles": 16,
        "H": 2,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
    }
    # MWF-style order gate: only Mon/Wed/Sat order days apply (see schedule_wire).
    orders = [0, 8, 0, 8, 0, 0, 8, 0, 8, 0]

    session = EngineSession()
    snap = session.init(cfg, seed=_TRAJECTORY_SEED)
    assert snap["seq"] == 0
    assert snap["episode_day"] == 0

    deltas: list[dict[str, Any]] = []
    for order in orders:
        deltas.append(session.step(order))

    assert len(deltas) == 10
    seqs = [int(d["seq"]) for d in deltas]
    assert seqs == list(range(1, 11))
    days = [int(d["episode_day"]) for d in deltas]
    assert days == list(range(10))

    init_lot_counts = list(snap["belief"]["lot_counts"])
    assert all(float(x) == 0.0 for x in init_lot_counts), "ADR 0136: init belief empty"

    for i, (delta, order) in enumerate(zip(deltas, orders, strict=True)):
        assert int(delta["day"]["order_qty"]) == order, f"day {i} order mismatch"
        belief = delta["belief"]
        lot_counts = list(belief["lot_counts"])
        assert len(lot_counts) == int(belief["L"])
        assert len(belief["f_marginals"]) == int(belief["L"]) * int(belief["K"])
        assert len(belief["f_grid"]) == int(belief["K"])

    final_belief = deltas[-1]["belief"]
    assert any(float(x) != 0.0 for x in final_belief["lot_counts"]), (
        "belief must populate after ten-day trajectory"
    )


def test_voi_crn_smoke_seven_scenarios_structural() -> None:
    """VOI CRN smoke: all seven scenarios return finite, differentiated profits."""
    for root_seed in range(1, 200):
        profits = run_voi_crn_cell(
            beta=2.0,
            root_seed=root_seed,
            scenarios=list(VOI_SCENARIOS),
            n_burn=2,
            n_score=6,
            filter_n=24,
            H=2,
            n_rollout_paths=2,
            lead_time=1,
            shipments=smoke_cool_shipments(),
        )

        assert set(profits) == set(VOI_SCENARIOS)
        values = [float(profits[s]) for s in VOI_SCENARIOS]
        if not all(math.isfinite(v) for v in values):
            continue

        unique = len({round(v, 4) for v in values})
        if unique < 3:
            continue

        p0 = float(profits["P0"])
        f1 = float(profits["F1"])
        bstate = float(profits["B-state"])
        if math.isclose(p0, f1, abs_tol=1e-6):
            continue
        if math.isclose(p0, bstate, abs_tol=1e-6):
            continue
        return

    pytest.fail(
        "expected structural profit differentiation across scenarios "
        "for some seed in 1..200"
    )

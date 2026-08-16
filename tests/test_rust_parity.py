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
from blueberries_voi.model import Cohort, ModelParams, day_step
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.model.constitutive import weibull_survival
from blueberries_voi.rng import STREAM_ALLOC, STREAM_DEMAND, STREAM_SPOIL, spawn_rng
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
    py = weibull_survival(3.0, beta=2.0, eta=14.0)
    rs = float(rust_core.weibull_survival_py(3.0, 2.0, 14.0))
    assert math.isclose(py, rs, rel_tol=0.0, abs_tol=1e-12)


def test_day_step_injected_smoke() -> None:
    """Injected demand path: Rust ``day_step_injected`` vs ``sim.rust_bridge`` shim."""
    counts_in = [20, 15]
    taus_in = [1.0, 3.0]
    lot_ids_in = [1, 2]
    demand = 12
    delivery_n, delivery_tau, delivery_lot = 8, 0.5, 3

    rs_counts, _rs_taus, _rs_lots, rs_dem, rs_sales, rs_waste = (
        rust_core.day_step_injected(
            counts_in,
            taus_in,
            lot_ids_in,
            demand,
            delivery_n,
            delivery_tau,
            delivery_lot,
            _DAY_STEP_SEED,
        )
    )

    assert int(rs_dem) == demand
    assert all(int(n) >= 0 for n in rs_counts)
    assert int(rs_sales) + int(rs_waste) <= sum(counts_in) + delivery_n

    cohorts = [
        Cohort(n=n, tau=t, lot_id=i)
        for n, t, i in zip(counts_in, taus_in, lot_ids_in, strict=True)
    ]
    delivery = Cohort(n=delivery_n, tau=delivery_tau, lot_id=delivery_lot)
    rng_d = spawn_rng(_DAY_STEP_SEED, run_id="parity", day=0, stream=STREAM_DEMAND)
    rng_a = spawn_rng(_DAY_STEP_SEED, run_id="parity", day=0, stream=STREAM_ALLOC)
    rng_s = spawn_rng(_DAY_STEP_SEED, run_id="parity", day=0, stream=STREAM_SPOIL)
    shim_result = day_step(
        cohorts,
        params=ModelParams(),
        demand=demand,
        delivery=delivery,
        rng_demand=rng_d,
        rng_alloc=rng_a,
        rng_spoil=rng_s,
    )

    assert int(shim_result.demand) == demand
    assert math.isclose(
        float(shim_result.sales_total), float(rs_sales), abs_tol=_STRUCTURAL_ATOL
    )
    shim_final = sum(c.n for c in shim_result.cohorts)
    rs_final = sum(int(n) for n in rs_counts)
    assert shim_final >= 0 and rs_final >= 0


def test_filter_step_one_day_smoke() -> None:
    """One-day filter update: normalized weights from Rust ``filter_step_py``."""
    counts = [[10, 5], [12, 3], [8, 7], [15, 2]]
    taus = [[1.0, 2.0], [0.5, 1.5], [2.0, 3.0], [1.5, 2.5]]
    sales, waste = 8, 1
    n = len(counts)
    uniform = 1.0 / n

    rs_weights = list(
        rust_core.filter_step_py(counts, taus, sales, waste, _FILTER_SEED)
    )
    assert len(rs_weights) == n
    assert all(w >= 0.0 for w in rs_weights)
    assert math.isclose(sum(rs_weights), 1.0, abs_tol=1e-9)
    assert any(not math.isclose(w, uniform, abs_tol=1e-12) for w in rs_weights)


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
    assert any(float(x) != 0.0 for x in init_lot_counts), "init belief empty"

    for i, (delta, order) in enumerate(zip(deltas, orders, strict=True)):
        assert int(delta["day"]["order_qty"]) == order, f"day {i} order mismatch"
        belief = delta["belief"]
        lot_counts = list(belief["lot_counts"])
        assert len(lot_counts) == int(belief["L"])
        assert len(belief["f_marginals"]) == int(belief["L"]) * int(belief["K"])
        assert len(belief["f_grid"]) == int(belief["K"])


def test_voi_crn_smoke_seven_scenarios_structural() -> None:
    """VOI CRN smoke: all seven scenarios return finite, differentiated profits."""
    profits = run_voi_crn_cell(
        beta=2.0,
        root_seed=_CRN_ROOT_SEED,
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
    assert all(math.isfinite(v) for v in values)

    unique = len({round(v, 4) for v in values})
    assert unique >= 3, (
        f"expected structural profit differentiation across scenarios, got {profits!r}"
    )

    p0 = float(profits["P0"])
    f1 = float(profits["F1"])
    bstate = float(profits["B-state"])
    assert not math.isclose(p0, f1, abs_tol=1e-6)
    assert not math.isclose(p0, bstate, abs_tol=1e-6)

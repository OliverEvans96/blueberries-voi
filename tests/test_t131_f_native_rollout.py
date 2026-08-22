"""T-131 f-native rollout forward-sim parity (Rust primary, ADR 0134)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Mapping

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.filter.belief import shelf_belief_from_oracle
from blueberries_voi.model import ModelParams, weibull_survival
from blueberries_voi.sim.alpha_tune import (
    DEFAULT_CI_ALPHAS,
    evaluate_alpha_episode_profit,
    tune_alpha_grid,
)
from blueberries_voi.sim.bakeoff_damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.sim.bakeoff_rollout import (
    detect_crn_desync,
    rollout_order,
    terminal_salvage_value,
    w_long_oldest_first,
)
from blueberries_voi.sim.shipments import smoke_cool_shipments

pytestmark = pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)

_CRN_ROOT_SEEDS: tuple[int, ...] = (11, 22, 33)
_PROFIT_ABS_TOL = 1e-6


def _table_belief() -> Any:
    f_grid = [0.0, 0.25, 0.5, 0.75, 1.0]
    return shelf_belief_from_oracle(
        lot_counts=[30, 15],
        f_marginals=[
            [0.0, 0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, 0.0, 0.0, 1.0],
        ],
        f_grid=f_grid,
    )


def test_no_repeat_delivery_over_horizon() -> None:
    """Delivery-once contract is locked in Rust `no_repeat_delivery_over_horizon`."""
    params = ModelParams()
    belief = _table_belief()
    base = DampedSurvivalWeightedPolicy(rho=0.8, alpha=0.9, params=params)
    q = rollout_order(
        belief,
        base_policy=base,
        params=params,
        rng_address={"root_seed": 42, "run_id": "rust-delivery-once"},
        H=3,
        n_rollout_paths=1,
        candidate_case_radius=0,
        pending_orders={},
        day=0,
        lead_time=1,
    )
    assert q >= 0
    assert q % params.case_size == 0


def test_w_long_weibull_helper_matches_python_on_fixture() -> None:
    """PyO3 Weibull helpers match cohort bakeoff_rollout (fallback path only)."""
    assert rust_core is not None
    lots = (
        {"n": 4, "tau": 6.0},
        {"n": 2, "tau": 2.0},
        {"n": 1, "tau": 0.0},
    )
    margin = 2.0
    params = ModelParams()
    py_vt = terminal_salvage_value(lots, margin=margin, params=params)
    weights = w_long_oldest_first(lots, params=params)
    freshness = []
    for lot in lots:
        n = int(lot["n"])
        tau = float(lot["tau"])
        f_val = max(0.0, 1.0 - tau / float(params.eta_ref))
        freshness.extend([f_val] * n)
    rust_vt = float(
        rust_core.terminal_salvage_unit_state_py(
            freshness,
            margin,
            float(params.beta),
            float(params.eta_ref),
        )
    )
    assert rust_vt == pytest.approx(py_vt, rel=0.0, abs=1e-9)
    for tau, w in zip((6.0, 2.0, 0.0), weights, strict=True):
        rust_w = float(
            rust_core.w_long_py(tau, float(params.beta), float(params.eta_ref))
        )
        assert rust_w == pytest.approx(
            weibull_survival(tau, beta=params.beta, eta=params.eta_ref),
            rel=0.0,
            abs=1e-12,
        )
        assert rust_w == pytest.approx(w, rel=0.0, abs=1e-12)


@pytest.mark.slow
def test_rollout_mean_profit_ge_base_sw_under_paired_crn() -> None:
    """Rollout arm via Rust alpha_tune ≥ damped-SW under paired CRN seeds."""
    ships = smoke_cool_shipments()
    base_profits: list[float] = []
    rollout_profits: list[float] = []
    for seed in _CRN_ROOT_SEEDS:
        base_profits.append(
            evaluate_alpha_episode_profit(
                "sw",
                0.9,
                int(seed),
                shipments=ships,
                n_burn=2,
                n_score=5,
                rollout_h=28,
                n_rollout_paths=8,
                candidate_case_radius=2,
            )
        )
        rollout_profits.append(
            evaluate_alpha_episode_profit(
                "rollout",
                0.9,
                int(seed),
                shipments=ships,
                n_burn=2,
                n_score=5,
                rollout_h=28,
                n_rollout_paths=8,
                candidate_case_radius=2,
            )
        )
    base_mean = sum(base_profits) / len(base_profits)
    rollout_mean = sum(rollout_profits) / len(rollout_profits)
    assert rollout_mean + _PROFIT_ABS_TOL >= base_mean


def test_costs_affect_ranking_fixture() -> None:
    """Higher waste_cost flips rollout winner on high-inventory fixture."""
    params = ModelParams()
    belief = _table_belief()

    class _FixedBase:
        def order(
            self,
            _belief: Any,
            *,
            day: int = 0,
            pending_orders: Mapping[int, int] | None = None,
        ) -> int:
            del _belief, day, pending_orders
            # Case neighbourhood where independent-aging rollout flips (Rust parity).
            return 48

    base = _FixedBase()
    rng_address: Mapping[str, Any] = {"root_seed": 7, "run_id": "cost-rank"}
    low_waste = rollout_order(
        belief,
        base_policy=base,
        params=params,
        rng_address=rng_address,
        H=4,
        n_rollout_paths=4,
        candidate_case_radius=2,
        waste_cost=0.0,
        day=6,
    )
    high_waste = rollout_order(
        belief,
        base_policy=base,
        params=params,
        rng_address=rng_address,
        H=4,
        n_rollout_paths=4,
        candidate_case_radius=2,
        waste_cost=100.0,
        day=6,
    )
    assert low_waste != high_waste


def test_tune_alpha_grid_rollout_uses_rust_kernel() -> None:
    """Rollout ladder arm scores through Rust when _core is present."""
    if not hasattr(rust_core, "evaluate_alpha_tune_episode_py"):
        pytest.skip("evaluate_alpha_tune_episode_py missing")
    ships = smoke_cool_shipments()
    best = tune_alpha_grid(
        "rollout",
        alphas=DEFAULT_CI_ALPHAS,
        root_seed=42,
        shipments=ships,
        n_burn=2,
        n_score=3,
    )
    assert best in DEFAULT_CI_ALPHAS
    profit = evaluate_alpha_episode_profit(
        "rollout",
        best,
        root_seed=42,
        shipments=ships,
        n_burn=2,
        n_score=3,
    )
    assert profit == profit  # finite
    assert profit > float("-inf")


def test_detect_crn_desync_gate() -> None:
    """ENG-04: matching stream addresses agree; crossed streams desync."""
    addr_a = {
        "root_seed": 11,
        "run_id": "t131-crn",
        "day": 0,
        "stream": ":demand",
    }
    addr_b = dict(addr_a)
    ok_match = detect_crn_desync(address_a=addr_a, address_b=addr_b)
    assert ok_match.ok
    addr_crossed = dict(addr_a)
    addr_crossed["stream"] = ":spoil"
    ok_cross = detect_crn_desync(address_a=addr_a, address_b=addr_crossed)
    assert not ok_cross.ok


@pytest.fixture(autouse=True)
def _rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")


def test_engine_session_act_rollout_skips_python_path_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rust-primary: EngineSession.act(rollout) must not call bakeoff _path_value."""
    from blueberries_voi.simulator import EngineSession

    called = False

    def _spy_path_value(*_args: object, **_kwargs: object) -> float:
        nonlocal called
        called = True
        raise AssertionError("Python _path_value must not run when _core is built")

    monkeypatch.setattr(
        "blueberries_voi.sim.bakeoff_rollout._path_value",
        _spy_path_value,
    )
    session = EngineSession()
    session.init(
        {
            "shipments": smoke_cool_shipments(),
            "n_particles": 32,
            "H": 3,
            "n_rollout_paths": 1,
            "candidate_case_radius": 1,
            "L": 2,
            "K": 4,
            "enable_filter": True,
        },
        seed=42,
    )
    session.act(policy="rollout")
    assert not called

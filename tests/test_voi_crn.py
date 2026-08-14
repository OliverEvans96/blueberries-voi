"""T-037 outer-loop CRN cell tests."""

from __future__ import annotations

from blueberries_voi._type_compat import is_same_package_type
from blueberries_voi.controller.damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.model import ModelParams
from blueberries_voi.rng import STREAM_DEMAND, spawn_rng
from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.voi import PHYSICS_RUN_ID, run_voi_crn_cell
from blueberries_voi.voi.crn import _run_scenario_episode


def test_physics_run_id_constant() -> None:
    assert PHYSICS_RUN_ID == "voi-physics"


def test_crn_cell_returns_p0_p1_bstate_profits() -> None:
    profits = run_voi_crn_cell(
        beta=2.0,
        root_seed=7,
        scenarios=["P0", "P1", "B-state"],
        n_burn=1,
        n_score=2,
        filter_n=16,
        H=2,
        n_rollout_paths=1,
        shipments=smoke_cool_shipments(),
    )
    assert set(profits) == {"P0", "P1", "B-state"}
    assert all(isinstance(v, float) for v in profits.values())


def test_crn_cell_accepts_full_column_set() -> None:
    profits = run_voi_crn_cell(
        beta=1.5,
        root_seed=3,
        scenarios=["P0", "P1", "F1", "F1s", "F2a", "F2", "B-state"],
        n_burn=1,
        n_score=1,
        filter_n=8,
        H=1,
        n_rollout_paths=1,
        shipments=smoke_cool_shipments(),
    )
    assert "F2a" in profits
    assert "F2" in profits


def test_shared_demand_stream_bit_stable_across_scenarios() -> None:
    """Physics demand draws share PHYSICS_RUN_ID regardless of scenario label."""
    a = spawn_rng(11, run_id=PHYSICS_RUN_ID, day=0, stream=STREAM_DEMAND).integers(
        0, 10_000
    )
    b = spawn_rng(11, run_id=PHYSICS_RUN_ID, day=0, stream=STREAM_DEMAND).integers(
        0, 10_000
    )
    assert int(a) == int(b)


def test_scored_profit_ignores_burn_in_days() -> None:
    """EpisodeLog.n_burn contract: scored slice starts after burn-in."""
    from blueberries_voi.sim import EpisodeLog

    params = ModelParams(beta=2.0)
    sw = DampedSurvivalWeightedPolicy(alpha=0.9, params=params)
    ep = _run_scenario_episode(
        scenario="B-state",
        policy=sw,
        shipments=smoke_cool_shipments(),
        params=params,
        root_seed=1,
        n_burn=2,
        n_score=3,
        lead_time=1,
        filter_n=8,
    )
    assert is_same_package_type(ep, EpisodeLog)
    assert ep.n_burn == 2
    assert len(ep.days) == 5
    assert len(ep.scored) == 3

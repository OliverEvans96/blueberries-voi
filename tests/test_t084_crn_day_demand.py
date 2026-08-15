"""T-084 CAL-B4 - CRN / VOI day-indexed demand wire (RED).

Locks ``.team/specs/T-084.md`` + ADR 0116 CRN identity:

* VOI CRN physics path passes calendar ``day`` into ``draw_demand`` / ``day_step``
* Demand RNG addressing stays ``(root_seed, PHYSICS_RUN_ID, day, :demand)``
* Two scenarios in one CRN cell share identical day-indexed ``DayLog.demand``
* Filter MC accepts/forwards ``day=`` without scenario-keyed demand streams
* X-06 cadence axis remains absent from VOI sweep config
"""

from __future__ import annotations

import pytest

pytest.skip("T-121 F3: Python CRN episode loop removed", allow_module_level=True)

import inspect
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.filter.backends import observation_loglik_mc
from blueberries_voi.filter.types import UNOBSERVED, RichObs, mask_for
from blueberries_voi.model import ModelParams, draw_demand, load_demand_profile
from blueberries_voi.rng import STREAM_DEMAND, spawn_rng
from blueberries_voi.sim.bakeoff_damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.voi import PHYSICS_RUN_ID
from blueberries_voi.voi.crn import _run_scenario_episode
from blueberries_voi.voi.sweep import VoISweepResult, run_voi_sweep

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMAND_PROFILE_PATH = _REPO_ROOT / "data" / "freshnet" / "demand_profile.json"

_ROOT_SEED = 11
_N_BURN = 1
_N_SCORE = 4  # multi-day episode (5 calendar days total)
_FILTER_N = 8


def _params_with_profile(*, beta: float = 2.0) -> ModelParams:
    assert _DEMAND_PROFILE_PATH.is_file(), (
        "committed data/freshnet/demand_profile.json required (T-080 / T-084)"
    )
    profile = load_demand_profile(_DEMAND_PROFILE_PATH)
    return ModelParams(beta=beta, demand_profile=profile)


def _expected_day_indexed_demands(
    *,
    params: ModelParams,
    root_seed: int,
    horizon: int,
) -> list[int]:
    """Independent CRN demand sequence: PHYSICS_RUN_ID + draw_demand(..., day=)."""
    out: list[int] = []
    for day in range(horizon):
        rng = spawn_rng(root_seed, run_id=PHYSICS_RUN_ID, day=day, stream=STREAM_DEMAND)
        out.append(int(draw_demand(rng, params, day=day)))
    return out


def _run_episode(scenario: str, params: ModelParams) -> Any:
    policy = DampedSurvivalWeightedPolicy(alpha=0.9, params=params)
    return _run_scenario_episode(
        scenario=scenario,
        policy=policy,
        shipments=smoke_cool_shipments(),
        params=params,
        root_seed=_ROOT_SEED,
        n_burn=_N_BURN,
        n_score=_N_SCORE,
        lead_time=1,
        filter_n=_FILTER_N,
    )


# ---------------------------------------------------------------------------
# AC: CRN physics path passes calendar day into demand draws
# ---------------------------------------------------------------------------


def test_crn_passes_calendar_day_into_draw_demand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VOI CRN day_step / draw_demand must receive episode day (not day=None)."""
    days_seen: list[int | None] = []
    real_day_step = _run_scenario_episode.__globals__["day_step"]

    def _spy(*args: Any, day: int | None = None, **kwargs: Any) -> Any:
        days_seen.append(day)
        return real_day_step(*args, day=day, **kwargs)

    monkeypatch.setitem(_run_scenario_episode.__globals__, "day_step", _spy)

    params = _params_with_profile()
    horizon = _N_BURN + _N_SCORE
    _run_episode("P0", params)

    assert days_seen, "CRN physics path must call day_step at least once"
    assert days_seen == list(range(horizon)), (
        "CRN must pass calendar day into day_step→draw_demand so μ(day) is "
        f"deterministic; got days={days_seen!r} expected {list(range(horizon))!r}"
    )


def test_crn_day_indexed_demand_matches_physics_addressed_draws() -> None:
    """DayLog.demand equals spawn_rng(PHYSICS_RUN_ID)+draw_demand(..., day=)."""
    params = _params_with_profile()
    horizon = _N_BURN + _N_SCORE
    ep = _run_episode("P0", params)
    got = [int(d.demand) for d in ep.days]
    expected = _expected_day_indexed_demands(
        params=params, root_seed=_ROOT_SEED, horizon=horizon
    )
    assert got == expected, (
        "CRN demand sequence must match day-indexed draws under "
        f"(root_seed, {PHYSICS_RUN_ID!r}, day, {STREAM_DEMAND!r}); "
        f"got={got!r} expected={expected!r}"
    )


# ---------------------------------------------------------------------------
# AC: Demand RNG addressing = (root_seed, PHYSICS_RUN_ID, day, :demand)
# ---------------------------------------------------------------------------


def test_demand_rng_addressing_uses_physics_run_id_not_scenario() -> None:
    """Demand stream is PHYSICS_RUN_ID-addressed; scenario label is not a key."""
    params = _params_with_profile()
    horizon = _N_BURN + _N_SCORE

    # Bit-stable spawn under PHYSICS_RUN_ID (never scenario id).
    for day in range(horizon):
        a = spawn_rng(
            _ROOT_SEED, run_id=PHYSICS_RUN_ID, day=day, stream=STREAM_DEMAND
        ).integers(0, 10_000, size=4)
        b = spawn_rng(
            _ROOT_SEED, run_id=PHYSICS_RUN_ID, day=day, stream=STREAM_DEMAND
        ).integers(0, 10_000, size=4)
        assert list(map(int, a)) == list(map(int, b))

        scenario_keyed = spawn_rng(
            _ROOT_SEED, run_id="voi-filter-P0", day=day, stream=STREAM_DEMAND
        ).integers(0, 10_000, size=4)
        assert list(map(int, a)) != list(map(int, scenario_keyed)), (
            "scenario-keyed run_id must not alias PHYSICS_RUN_ID demand stream"
        )

    ep = _run_episode("P1", params)
    got = [int(d.demand) for d in ep.days]
    expected = _expected_day_indexed_demands(
        params=params, root_seed=_ROOT_SEED, horizon=horizon
    )
    assert got == expected


def test_changing_only_scenario_label_does_not_change_demand_draws() -> None:
    """Same root seed / PHYSICS_RUN_ID / days → identical demands across labels."""
    params = _params_with_profile()
    ep_a = _run_episode("P0", params)
    ep_b = _run_episode("F1", params)
    demands_a = [int(d.demand) for d in ep_a.days]
    demands_b = [int(d.demand) for d in ep_b.days]
    assert demands_a == demands_b
    assert demands_a == _expected_day_indexed_demands(
        params=params,
        root_seed=_ROOT_SEED,
        horizon=_N_BURN + _N_SCORE,
    )


# ---------------------------------------------------------------------------
# AC: Two scenarios → identical DayLog.demand under calendar profile
# ---------------------------------------------------------------------------


def test_two_scenarios_identical_demand_sequences_under_profile() -> None:
    """Regression: one CRN cell, two scenarios, identical multi-day demand."""
    params = _params_with_profile()
    ep_p0 = _run_episode("P0", params)
    ep_p1 = _run_episode("P1", params)
    assert len(ep_p0.days) == _N_BURN + _N_SCORE
    assert len(ep_p1.days) == _N_BURN + _N_SCORE
    demands_p0 = [int(d.demand) for d in ep_p0.days]
    demands_p1 = [int(d.demand) for d in ep_p1.days]
    assert demands_p0 == demands_p1, (
        "scenarios in one CRN cell must share identical DayLog.demand under "
        f"the calendar profile; P0={demands_p0!r} P1={demands_p1!r}"
    )
    # Lock day-index wiring: identity alone is insufficient if both omit day=.
    assert demands_p0 == _expected_day_indexed_demands(
        params=params,
        root_seed=_ROOT_SEED,
        horizon=_N_BURN + _N_SCORE,
    )


# ---------------------------------------------------------------------------
# AC: Filter MC / shared kernels compile-run with day= signature
# ---------------------------------------------------------------------------


def test_observation_loglik_mc_accepts_day_kwarg() -> None:
    """Filter MC must expose keyword-only day= (or equivalent) for calendar μ."""
    sig = inspect.signature(observation_loglik_mc)
    assert "day" in sig.parameters, (
        "observation_loglik_mc must accept day= so shared day_step/draw_demand "
        "can use μ(day) without scenario-keyed demand streams; "
        f"params={list(sig.parameters)}"
    )
    day_param = sig.parameters["day"]
    assert day_param.kind is inspect.Parameter.KEYWORD_ONLY, (
        "day must be keyword-only on observation_loglik_mc"
    )


def test_observation_loglik_mc_forwards_day_without_scenario_demand_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MC path forwards day into day_step/draw_demand; no scenario demand key."""
    sig = inspect.signature(observation_loglik_mc)
    assert "day" in sig.parameters, (
        "observation_loglik_mc must accept day= before forwarding can be asserted; "
        f"params={list(sig.parameters)}"
    )
    assert "scenario" not in sig.parameters

    days_seen: list[int | None] = []
    real_day_step = observation_loglik_mc.__globals__["day_step"]

    def _spy(*args: Any, day: int | None = None, **kwargs: Any) -> Any:
        days_seen.append(day)
        return real_day_step(*args, day=day, **kwargs)

    monkeypatch.setitem(observation_loglik_mc.__globals__, "day_step", _spy)

    params = _params_with_profile()
    counts = np.full((2, 2), 4, dtype=int)
    ages = np.linspace(1.0, 3.0, 2)
    obs = mask_for("P1").apply(
        RichObs(
            arrivals=0,
            sales_total=8,
            waste_total=1,
            sales_by_lot=UNOBSERVED,
            waste_by_lot=UNOBSERVED,
            pack_date=UNOBSERVED,
            age_at_receipt=UNOBSERVED,
            lot_ids_live=UNOBSERVED,
        )
    )
    rng = np.random.default_rng(3)
    calendar_day = 3

    observation_loglik_mc(
        counts,
        ages,
        obs,
        params,
        rng,
        n_mc=1,
        day=calendar_day,
    )
    assert days_seen, "observation_loglik_mc must call day_step"
    assert all(d == calendar_day for d in days_seen), (
        f"filter MC must forward day={calendar_day} into day_step→draw_demand; "
        f"got {days_seen!r}"
    )


# ---------------------------------------------------------------------------
# AC: X-06 cadence axis remains absent from VOI sweep config
# ---------------------------------------------------------------------------


def test_voi_sweep_has_no_cadence_axis() -> None:
    """X-06 stays parked: sweep is scenario x β only (no cadence dimension)."""
    forbidden = {
        "cadence",
        "delivery_cadence",
        "cadences",
        "stagger",
        "arrival_stagger",
        "staggering",
    }
    sweep_params = set(inspect.signature(run_voi_sweep).parameters)
    assert sweep_params.isdisjoint(forbidden), (
        f"run_voi_sweep must not expose cadence/stagger axes; found "
        f"{sorted(sweep_params & forbidden)}"
    )

    result_fields = {f.name for f in fields(VoISweepResult)}
    assert result_fields.isdisjoint(forbidden), (
        f"VoISweepResult must not carry cadence fields; found "
        f"{sorted(result_fields & forbidden)}"
    )

    # Smoke shape lock: JSON surface stays scenario x beta.
    result = run_voi_sweep(
        smoke=True,
        root_seed=2,
        scenarios=["P0", "P1"],
        n_replications=1,
        n_bootstrap=8,
    )
    payload = result.to_jsonable()
    assert "cadence" not in payload
    assert "betas" in payload and "scenarios" in payload
    assert "arms" in payload


def test_crn_cell_params_accept_demand_profile_without_cadence_knob() -> None:
    """CRN cell takes ModelParams (incl. profile); no cadence sweep knob."""
    from blueberries_voi.voi import run_voi_crn_cell

    sig = inspect.signature(run_voi_crn_cell)
    assert "params" in sig.parameters
    assert "cadence" not in sig.parameters
    params = replace(_params_with_profile(), beta=1.5)
    profits = run_voi_crn_cell(
        beta=1.5,
        root_seed=_ROOT_SEED,
        scenarios=["P0", "P1"],
        n_burn=_N_BURN,
        n_score=2,
        filter_n=_FILTER_N,
        H=1,
        n_rollout_paths=1,
        shipments=smoke_cool_shipments(),
        params=params,
    )
    assert set(profits) == {"P0", "P1"}

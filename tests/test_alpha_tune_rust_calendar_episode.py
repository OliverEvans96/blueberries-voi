"""Rust calendar alpha_tune episode correctness (T-133 follow-up).

Validates the f-native Rust kernel used by notebook 12 when
``USE_CALENDAR_DEMAND=True``. Python cohort episodes are a legacy reference
only (ADR 0130); parity is not required, but demand draws and BO monotonicity
must hold on full-run horizons.
"""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.model import ModelParams
from blueberries_voi.model.demand_profile import DemandProfile, load_demand_profile
from blueberries_voi.rng import STREAM_DEMAND
from blueberries_voi.sim.alpha_tune import evaluate_alpha_episode_outcomes
from blueberries_voi.sim.profit import ProfitCosts
from blueberries_voi.sim.shipments import smoke_cool_shipments

_REPO = Path(__file__).resolve().parents[1]
_PROFILE_PATH = _REPO / "data" / "freshnet" / "demand_profile.json"
_BO_SEEDS = [401_902_531, 434_395_762, 1_417_981_267, 1_562_808_462]
_RUN_ID = "alpha-tune"
_NOTEBOOK_COSTS = ProfitCosts(unit_margin=2.0, waste_cost=5.0, stockout_penalty=3.0)
_FULL_RUN = dict(n_burn=28, n_score=28, lead_time=1)
_SMOKE = dict(n_burn=2, n_score=5, lead_time=1)


def _committed_profile() -> DemandProfile:
    return load_demand_profile(_PROFILE_PATH)


def _params_with_profile(profile: DemandProfile | None = None) -> ModelParams:
    prof = profile if profile is not None else _committed_profile()
    return ModelParams(demand_profile=prof)


def _core_profile(prof: DemandProfile) -> object:
    assert rust_core is not None
    return rust_core.DemandProfile(
        prof.scale_target_mu,
        list(prof.dow_factors),
        list(prof.week_factors),
        prof.demand_vm,
    )


@pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)
def test_draw_demand_at_day_py_is_deterministic_and_uses_calendar_mu() -> None:
    """Rust demand draws are stable and track profile μ(day) (not Python bit-parity)."""
    fn = getattr(rust_core, "draw_demand_at_day_py", None)
    if fn is None:
        pytest.skip("draw_demand_at_day_py not exported")
    prof = _committed_profile()
    core_prof = _core_profile(prof)
    params = _params_with_profile(prof)
    for seed in (42, 99, 1_417_981_267):
        for day in (0, 3, 6, 13):
            kwargs = dict(
                root_seed=int(seed),
                run_id=_RUN_ID,
                day=int(day),
                demand_mu=float(params.demand_mu),
                demand_vm=float(params.demand_vm),
                demand_profile=core_prof,
                stream=STREAM_DEMAND,
            )
            a = int(fn(**kwargs))
            b = int(fn(**kwargs))
            assert a == b, f"seed={seed} day={day}: rust draw not deterministic"
            flat = int(
                fn(
                    int(seed),
                    _RUN_ID,
                    int(day),
                    float(prof.scale_target_mu),
                    float(prof.demand_vm),
                    None,
                    STREAM_DEMAND,
                )
            )
            # Calendar vs flat constant μ should usually differ for FreshNet days.
            if day in (0, 3, 6):
                assert a != flat or b != flat


@pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)
def test_rust_calendar_full_run_alpha_monotone_in_mean() -> None:
    """Full-run BO horizon: higher alpha should raise mean profit (notebook seeds)."""
    params = _params_with_profile()
    ships = smoke_cool_shipments()
    kwargs = dict(
        params=params,
        costs=_NOTEBOOK_COSTS,
        shipments=ships,
        rho=0.8,
        **_FULL_RUN,
    )

    def mean_profit(alpha: float) -> float:
        vals = [
            evaluate_alpha_episode_outcomes("sw", alpha, seed, **kwargs).profit
            for seed in _BO_SEEDS
        ]
        return float(statistics.mean(vals))

    assert mean_profit(0.9) > mean_profit(0.5)


@pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)
def test_rust_calendar_smoke_horizon_is_high_variance() -> None:
    """Short smoke horizon (2+5) is unsuitable for BO — documents notebook pitfall."""
    params = _params_with_profile()
    ships = smoke_cool_shipments()
    kwargs = dict(
        params=params,
        costs=_NOTEBOOK_COSTS,
        shipments=ships,
        rho=0.8,
        **_SMOKE,
    )
    profits = [
        evaluate_alpha_episode_outcomes("sw", 0.9, seed, **kwargs).profit
        for seed in _BO_SEEDS
    ]
    mean = statistics.mean(profits)
    stdev = statistics.pstdev(profits)
    # Smoke window: at least one seed diverges strongly from the mean.
    assert max(abs(p - mean) for p in profits) > 100.0
    assert stdev > 50.0


@pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)
def test_rust_calendar_profit_finite_full_run() -> None:
    params = _params_with_profile()
    ships = smoke_cool_shipments()
    out = evaluate_alpha_episode_outcomes(
        "sw",
        0.9,
        42,
        params=params,
        costs=_NOTEBOOK_COSTS,
        shipments=ships,
        **_FULL_RUN,
    )
    assert out.profit == out.profit  # finite
    assert out.total_waste >= 0
    assert out.total_lost_sales >= 0

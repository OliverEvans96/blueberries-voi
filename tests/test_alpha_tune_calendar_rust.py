"""T-133: Rust alpha_tune with typed calendar DemandProfile."""

from __future__ import annotations

from pathlib import Path

import pytest

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.model import ModelParams
from blueberries_voi.model.demand_profile import DemandProfile, load_demand_profile
from blueberries_voi.sim.alpha_tune import evaluate_alpha_episode_outcomes
from blueberries_voi.sim.profit import DEFAULT_PROFIT_COSTS
from blueberries_voi.sim.shipments import smoke_cool_shipments

_REPO = Path(__file__).resolve().parents[1]
_PROFILE_PATH = _REPO / "data" / "freshnet" / "demand_profile.json"


def _committed_profile() -> DemandProfile:
    return load_demand_profile(_PROFILE_PATH)


def _params_with_profile(profile: DemandProfile | None = None) -> ModelParams:
    prof = profile if profile is not None else _committed_profile()
    return ModelParams(demand_profile=prof)


@pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)
def test_core_demand_profile_mu_matches_python() -> None:
    prof = _committed_profile()
    core_prof = rust_core.DemandProfile(
        prof.scale_target_mu,
        list(prof.dow_factors),
        list(prof.week_factors),
        prof.demand_vm,
    )
    for day in (0, 6, 7, 13, 89):
        assert core_prof.mu(day) == pytest.approx(prof.mu(day), rel=0.0, abs=1e-9)


@pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)
def test_rust_alpha_tune_sw_calendar_reproducible() -> None:
    """Rust calendar episode is deterministic and uses the typed profile wire."""
    params = _params_with_profile()
    ships = smoke_cool_shipments()
    kwargs = dict(
        alpha=0.9,
        root_seed=42,
        rho=0.8,
        params=params,
        costs=DEFAULT_PROFIT_COSTS,
        shipments=ships,
        n_burn=2,
        n_score=3,
        lead_time=1,
    )
    a = evaluate_alpha_episode_outcomes("sw", **kwargs)
    b = evaluate_alpha_episode_outcomes("sw", **kwargs)
    assert a == b
    assert a.profit != 0.0


@pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)
def test_rust_calendar_profile_changes_outcomes() -> None:
    """Calendar profile must change Rust scored outcomes vs flat-μ defaults."""
    ships = smoke_cool_shipments()
    base = dict(
        alpha=0.9,
        root_seed=42,
        rho=0.8,
        costs=DEFAULT_PROFIT_COSTS,
        shipments=ships,
        n_burn=2,
        n_score=3,
        lead_time=1,
    )
    flat = evaluate_alpha_episode_outcomes("sw", params=ModelParams(), **base)
    cal = evaluate_alpha_episode_outcomes("sw", params=_params_with_profile(), **base)
    assert cal != flat


@pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)
def test_rust_kernel_used_with_calendar_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calendar profile must not skip the Rust kernel."""
    from blueberries_voi.sim import alpha_tune as mod

    params = _params_with_profile()
    ships = smoke_cool_shipments()
    sentinel = mod.AlphaTuneEpisodeOutcomes(
        profit=123.456,
        total_waste=1,
        total_lost_sales=2,
        fill_rate=0.99,
        day_no_stockout_rate=0.9,
    )

    def _fake_rust(*_args: object, **_kwargs: object) -> mod.AlphaTuneEpisodeOutcomes:
        return sentinel

    monkeypatch.setattr(mod, "_evaluate_via_rust_kernel", _fake_rust)
    got = mod.evaluate_alpha_episode_outcomes(
        "sw",
        0.9,
        42,
        params=params,
        shipments=ships,
        n_burn=2,
        n_score=3,
    )
    assert got is sentinel

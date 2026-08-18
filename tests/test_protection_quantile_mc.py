"""T-132: heterogeneous protection-interval demand quantile (MC / CAL-B4)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from scipy.stats import nbinom

from blueberries_voi.model import ModelParams
from blueberries_voi.model.demand_profile import DemandProfile, load_demand_profile
from blueberries_voi.sim.bakeoff_damped_sw import (
    DampedSurvivalWeightedPolicy,
    protection_demand_quantile,
)
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE

_REPO = Path(__file__).resolve().parents[1]
_PROFILE_PATH = _REPO / "data" / "freshnet" / "demand_profile.json"
_ALPHA = 0.9


def _homogeneous_closed_form(
    alpha: float, params: ModelParams, protection_days: int
) -> float:
    r = float(params.nb_r()) * float(protection_days)
    p = float(params.nb_p())
    return float(nbinom.ppf(float(alpha), r, p))


def _committed_profile() -> DemandProfile:
    return load_demand_profile(_PROFILE_PATH)


def _params_with_profile(profile: DemandProfile | None = None) -> ModelParams:
    prof = profile if profile is not None else _committed_profile()
    return ModelParams(demand_profile=prof)


def test_homogeneous_no_profile_matches_scipy() -> None:
    params = ModelParams()
    for n in (2, 3, 4):
        got = protection_demand_quantile(_ALPHA, params, protection_days=n, start_day=0)
        want = _homogeneous_closed_form(_ALPHA, params, n)
        assert got == pytest.approx(want, rel=0.0, abs=1e-9)


def test_flat_profile_matches_homogeneous_closed_form() -> None:
    flat = DemandProfile(
        scale_target_mu=30.0,
        dow_factors=(1.0,) * 7,
        week_factors=(1.0,),
        demand_vm=2.0,
    )
    params = ModelParams(demand_profile=flat)
    got = protection_demand_quantile(_ALPHA, params, protection_days=4, start_day=3)
    want = _homogeneous_closed_form(_ALPHA, params, 4)
    assert got == pytest.approx(want, rel=0.0, abs=1e-9)


def test_heterogeneous_window_exceeds_flat_mu() -> None:
    """Constructed weekend uplift profile beats flat-μ closed form."""
    weekend_profile = DemandProfile(
        scale_target_mu=30.0,
        dow_factors=(1.0, 1.0, 1.0, 1.0, 1.0, 1.5, 1.5),
        week_factors=(1.0,),
        demand_vm=2.0,
    )
    params = ModelParams(demand_profile=weekend_profile)
    flat_params = ModelParams(demand_mu=30.0)
    prot = 2
    start_day = 5  # Saturday + Sunday at 1.5x scale
    het = protection_demand_quantile(
        _ALPHA, params, protection_days=prot, start_day=start_day
    )
    flat = protection_demand_quantile(
        _ALPHA, flat_params, protection_days=prot, start_day=start_day
    )
    assert het > flat + 5.0, f"expected uplifted weekend window > flat; {het} vs {flat}"


def test_start_day_changes_quantile() -> None:
    params = _params_with_profile()
    a = protection_demand_quantile(_ALPHA, params, protection_days=3, start_day=1)
    b = protection_demand_quantile(_ALPHA, params, protection_days=3, start_day=6)
    assert a != b


def test_mc_deterministic() -> None:
    params = _params_with_profile()
    kwargs = dict(
        alpha=_ALPHA,
        protection_days=4,
        start_day=3,
        n_mc=10_000,
    )
    a = protection_demand_quantile(params=params, **kwargs)
    b = protection_demand_quantile(params=params, **kwargs)
    assert a == b


def test_sw_order_differs_with_profile() -> None:
    from blueberries_voi.filter.belief import shelf_belief_from_oracle

    belief = shelf_belief_from_oracle(
        lot_counts=[0.0],
        f_marginals=[[0.0, 0.0, 0.0, 0.0, 1.0]],
        f_grid=[0.0, 0.25, 0.5, 0.75, 1.0],
    )
    flat = DampedSurvivalWeightedPolicy(
        alpha=_ALPHA,
        rho=1.0,
        params=ModelParams(),
        schedule=DEFAULT_ORDER_SCHEDULE,
    )
    cal = DampedSurvivalWeightedPolicy(
        alpha=_ALPHA,
        rho=1.0,
        params=_params_with_profile(),
        schedule=DEFAULT_ORDER_SCHEDULE,
    )
    day = 3  # Thursday
    q_flat = flat.order(belief, day=day, pending_orders={})
    q_cal = cal.order(belief, day=day, pending_orders={})
    assert q_cal != q_flat


def test_rust_python_protection_quantile_parity() -> None:
    rust_core = importlib.import_module("blueberries_voi.backend").rust_core
    if rust_core is None:
        pytest.skip("blueberries_voi._core not built")
    fn = getattr(rust_core, "protection_demand_quantile_py", None)
    if fn is None:
        pytest.skip("protection_demand_quantile_py not exported")
    profile = _committed_profile()
    params = _params_with_profile(profile)
    py = protection_demand_quantile(_ALPHA, params, protection_days=3, start_day=6)
    core_prof = rust_core.DemandProfile(
        profile.scale_target_mu,
        list(profile.dow_factors),
        list(profile.week_factors),
        profile.demand_vm,
    )
    rs = float(
        fn(
            _ALPHA,
            params.demand_mu,
            params.demand_vm,
            3,
            6,
            core_prof,
        )
    )
    assert py == pytest.approx(rs, rel=0.0, abs=1.0)

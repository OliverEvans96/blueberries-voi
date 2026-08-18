"""Coverage for Wave F retained Python façades (ADR 0127 orchestration layer)."""

from __future__ import annotations

import importlib
import warnings

import numpy as np
import pytest

from blueberries_voi.model.constitutive import (
    allocate_sales,
    death_prob_hazard_product,
    death_prob_survival_ratio,
    draw_demand,
    picking_weights,
    q10_age_increment,
    weibull_survival,
)
from blueberries_voi.model.params import Cohort, ModelParams
from blueberries_voi.sim import rust_bridge


def test_constitutive_formulas_smoke() -> None:
    assert weibull_survival(0.0, beta=2.0, eta=14.0) == 1.0
    assert 0.0 < weibull_survival(3.0, beta=2.0, eta=14.0) < 1.0
    with pytest.raises(ValueError, match="eta"):
        weibull_survival(1.0, beta=2.0, eta=0.0)
    assert death_prob_survival_ratio(1.0, 0.5, beta=2.0, eta=14.0) >= 0.0
    assert death_prob_hazard_product(0.0, 0.5, beta=2.0, eta=14.0) == 0.0
    assert q10_age_increment(1.0, t_store_c=4.0, t_ref_c=0.0, q10=2.0) > 0.0
    weights = picking_weights([1.0, 2.0], sigma=1.0, beta=2.0, eta=14.0)
    assert weights.shape == (2,)
    assert np.isclose(float(weights.sum()), 1.0)
    rng = np.random.default_rng(0)
    sales = allocate_sales([5, 3], demand=4, weights=weights, rng=rng)
    assert int(sales.sum()) == 4
    params = ModelParams()
    demand = draw_demand(rng, params, day=0)
    assert demand >= 0


def test_rust_bridge_requires_demand(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)
    cohorts = [Cohort(n=5, tau=1.0, lot_id=1)]
    with pytest.raises(RuntimeError, match="requires rust backend and fixed demand"):
        rust_bridge.day_step(cohorts, params=ModelParams(), demand=None)


def test_rust_bridge_python_stochastic_path_with_rng_demand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Open-loop callers may draw demand in Python even when the Rust backend is on."""
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)
    params = ModelParams()
    cohorts = [Cohort(n=5, tau=1.0, lot_id=1)]
    rng_d = np.random.default_rng(0)
    rng_a = np.random.default_rng(1)
    rng_s = np.random.default_rng(2)
    result = rust_bridge.day_step(
        cohorts,
        params=params,
        rng_demand=rng_d,
        rng_alloc=rng_a,
        rng_spoil=rng_s,
        day=3,
    )
    assert result.demand >= 0
    assert result.sales_total >= 0
    assert result.waste_total >= 0
    assert all(c.tau > 1.0 for c in result.cohorts)


def test_rust_bridge_python_fixed_demand_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fixed-demand path uses Python cohort kernel when day_step_injected is absent."""
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)
    params = ModelParams()
    cohorts = [Cohort(n=4, tau=2.0, lot_id=7)]
    rng_a = np.random.default_rng(4)
    rng_s = np.random.default_rng(5)
    result = rust_bridge.day_step(
        cohorts,
        params=params,
        demand=6,
        rng_alloc=rng_a,
        rng_spoil=rng_s,
    )
    assert result.demand == 6
    assert result.sales_total <= 6
    assert result.waste_total >= 0


def test_rust_bridge_python_day_step_delivery_and_empty_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "python")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)
    params = ModelParams()
    delivery = Cohort(n=3, tau=0.5, lot_id=9)
    result = rust_bridge.day_step(
        [],
        params=params,
        demand=0,
        delivery=delivery,
        rng_alloc=np.random.default_rng(0),
        rng_spoil=np.random.default_rng(1),
    )
    assert len(result.cohorts) == 1
    assert result.cohorts[0].n == 3
    assert result.cohorts[0].lot_id == 9


def test_rust_bridge_python_day_step_requires_rng_when_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "python")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)
    cohorts = [Cohort(n=2, tau=1.0, lot_id=1)]
    with pytest.raises(ValueError, match="rng_alloc required"):
        rust_bridge.day_step(
            cohorts,
            params=ModelParams(),
            demand=1,
            rng_alloc=None,
            rng_spoil=np.random.default_rng(0),
        )


def test_backend_warn_fallback_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)
    backend_mod._WARNED = False
    backend_mod.rust_core = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        backend_mod.warn_fallback_once()
        backend_mod.warn_fallback_once()
    assert len(caught) == 1
    assert backend_mod.rust_available() is False

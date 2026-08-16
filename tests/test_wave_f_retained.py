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

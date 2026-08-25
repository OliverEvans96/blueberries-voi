"""Parity checks for PyO3 helpers used by doc-figure scripts (Wave 1)."""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest

from blueberries_voi.backend import rust_core as _maybe_core

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

rust_core = _maybe_core

REPO_ROOT = Path(__file__).resolve().parents[1]
ARRIVAL_JSON = REPO_ROOT / "data" / "abdella" / "arrival_model.json"


@pytest.fixture(autouse=True)
def _rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)


def _ref_picking_weights_f(
    freshness: list[float], *, sigma: float, uniform: bool
) -> list[float]:
    if uniform or sigma <= 0.0 or not freshness:
        n = len(freshness)
        return [1.0 / n] * n
    raw = [max(f, 0.0) ** sigma for f in freshness]
    total = sum(raw)
    return [w / total for w in raw]


def test_picking_weights_f_py_matches_reference() -> None:
    f_vals = [0.2, 0.5, 0.9]
    w = rust_core.picking_weights_f_py(f_vals, 0.5, False)
    ref = _ref_picking_weights_f(f_vals, sigma=0.5, uniform=False)
    assert len(w) == len(ref)
    np.testing.assert_allclose(w, ref, rtol=0, atol=1e-12)
    assert abs(sum(w) - 1.0) < 1e-12
    assert w[0] < w[1] < w[2]


def test_draw_gamma_decrement_samples_warm_mean_exceeds_cold() -> None:
    n = 4000
    seed = 42
    cold = rust_core.draw_gamma_decrement_samples_py(n, 0.0, seed)
    warm = rust_core.draw_gamma_decrement_samples_py(n, 8.0, seed)
    assert len(cold) == n
    assert len(warm) == n
    assert np.mean(warm) > np.mean(cold)


def test_arrival_marginal_cdf_prior_endpoints_sane() -> None:
    grid = np.linspace(0.0, 1.0, 81)
    cdf = rust_core.arrival_marginal_cdf_py(
        str(ARRIVAL_JSON), "prior", grid.tolist()
    )
    assert len(cdf) == len(grid)
    assert 0.0 <= cdf[0] <= 1.0
    assert cdf[-1] >= 0.99
    assert cdf[0] <= cdf[-1]
    for i in range(1, len(cdf)):
        assert cdf[i] >= cdf[i - 1] - 1e-12

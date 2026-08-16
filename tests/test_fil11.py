"""FIL-11 viz helpers - Stage B/C diagnostic runners (Stage A documented FAIL)."""

from __future__ import annotations

import pytest

pytest.skip(
    "T-121 F3: fil11 uses removed particle_filter path", allow_module_level=True
)

from typing import TYPE_CHECKING

import numpy as np
import pytest

from blueberries_voi.filter.constants import PRODUCTION_N
from blueberries_voi.filter.types import age_grid
from blueberries_voi.viz.fil11 import (
    _arrival_prior,
    _spread,
    run_fil11_stage_b,
    run_fil11_stage_c,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_spread_of_uniform_prior() -> None:
    grid = age_grid(8)
    prior = np.ones(8) / 8.0
    s = _spread(prior, grid)
    assert s > 0.0


def test_arrival_prior_small_sample() -> None:
    prior = _arrival_prior(1.0, K=8, n_samples=40)
    assert prior.shape == (8,)
    assert abs(float(prior.sum()) - 1.0) < 1e-6


def test_stage_b_smoke(tmp_path: Path) -> None:
    # Diagnostic only after Stage A fail - exercises calibration helper.
    # Small N / short score window: MF age update is O(N) per day (T-021).
    result = run_fil11_stage_b(
        n_reps=1,
        n_particles=4,
        K=4,
        L=2,
        n_burn=1,
        n_score=2,
        figures_dir=tmp_path,
    )
    assert result.n_reps == 1
    assert result.n_particles == 4
    assert result.K == 4
    assert result.figure_path.is_file()
    assert 0.0 <= result.coverage_90 <= 1.0
    assert 0.0 <= result.rank_mean <= 1.0
    assert result.rank_std >= 0.0


def test_stage_b_defaults_use_production_n() -> None:
    """Production particle count is the default (smoke overrides for speed)."""
    kw = run_fil11_stage_b.__kwdefaults__
    assert kw is not None
    assert kw["n_particles"] == PRODUCTION_N
    assert kw["n_reps"] == 50


def test_stage_c_smoke(tmp_path: Path) -> None:
    """Generative Stage C under production MC LL (ADR 0088 / T-012)."""
    result = run_fil11_stage_c(L=2, K=4, figures_dir=tmp_path, n_obs_samples=80)
    assert result.figure_path.is_file()
    assert result.mode == "generative_day_step"
    assert result.passed
    assert result.divergence <= result.tolerance
    assert result.n_support > 1
    assert result.L == 2
    assert result.K == 4


def test_stage_c_wrong_physics_fails(tmp_path: Path) -> None:
    """Injected wrong-physics observation model must fail Stage C."""
    result = run_fil11_stage_c(
        L=2,
        K=4,
        figures_dir=tmp_path,
        n_obs_samples=80,
        inject_wrong_physics=True,
    )
    assert result.mode == "generative_day_step"
    assert result.passed is False
    assert result.divergence > result.tolerance
    assert result.n_support > 1
    assert result.figure_path.is_file()


def test_age_grid_rejects_small_k() -> None:
    with pytest.raises(ValueError, match="K must be"):
        age_grid(1)

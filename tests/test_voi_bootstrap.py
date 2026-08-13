"""T-038 paired bootstrap CI tests (VOI-03)."""

from __future__ import annotations

import numpy as np
import pytest

from blueberries_voi.voi import paired_bootstrap_ci


def test_paired_bootstrap_resamples_difference_indices() -> None:
    deltas = [1.0, 2.0, 3.0, 4.0]
    rng = np.random.default_rng(0)
    ci = paired_bootstrap_ci(deltas, n_bootstrap=200, alpha=0.05, rng=rng)
    assert ci.mean == pytest.approx(2.5)
    assert ci.low <= ci.mean <= ci.high
    assert ci.n_bootstrap == 200


def test_paired_bootstrap_reproducible_with_seed() -> None:
    deltas = [0.5, -0.2, 1.1, 0.0, 0.3]
    a = paired_bootstrap_ci(deltas, n_bootstrap=50, rng=np.random.default_rng(123))
    b = paired_bootstrap_ci(deltas, n_bootstrap=50, rng=np.random.default_rng(123))
    assert a.mean == b.mean
    assert a.low == b.low
    assert a.high == b.high


def test_paired_bootstrap_rejects_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        paired_bootstrap_ci([], n_bootstrap=10, rng=np.random.default_rng(0))

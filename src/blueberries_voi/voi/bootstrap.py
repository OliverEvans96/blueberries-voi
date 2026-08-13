"""VOI-03 paired bootstrap CI on per-replication differences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "BootstrapCI",
    "paired_bootstrap_ci",
]


@dataclass(frozen=True)
class BootstrapCI:
    """Point estimate (mean) plus percentile CI from paired differences."""

    mean: float
    low: float
    high: float
    n_bootstrap: int
    alpha: float


def paired_bootstrap_ci(
    deltas: Sequence[float],
    *,
    n_bootstrap: int,
    alpha: float = 0.05,
    rng: np.random.Generator,
) -> BootstrapCI:
    """Mean + (low, high) percentile CI by resampling paired difference indices.

    Does **not** shuffle unpaired scenario/P0 labels — only replication indices
    of the already-paired ``deltas`` array are drawn with replacement.
    """
    if n_bootstrap <= 0:
        msg = f"n_bootstrap must be positive, got {n_bootstrap}"
        raise ValueError(msg)
    if not 0.0 < float(alpha) < 1.0:
        msg = f"alpha must be in (0, 1), got {alpha}"
        raise ValueError(msg)
    arr = np.asarray(list(deltas), dtype=float)
    if arr.size == 0:
        msg = "deltas must be non-empty"
        raise ValueError(msg)
    n = int(arr.size)
    means = np.empty(int(n_bootstrap), dtype=float)
    for b in range(int(n_bootstrap)):
        idx = rng.integers(0, n, size=n)
        means[b] = float(np.mean(arr[idx]))
    low_q = 100.0 * (float(alpha) / 2.0)
    high_q = 100.0 * (1.0 - float(alpha) / 2.0)
    return BootstrapCI(
        mean=float(np.mean(arr)),
        low=float(np.percentile(means, low_q)),
        high=float(np.percentile(means, high_q)),
        n_bootstrap=int(n_bootstrap),
        alpha=float(alpha),
    )

"""Survival-weighted on-hand expectation under joint or product marginals."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.model import ModelParams, weibull_survival

from .mean_field_diag import marginals_from_joint

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray


def survival_weighted_on_hand(
    n: Sequence[int | float],
    joint_or_marginals: NDArray[np.floating],
    *,
    params: ModelParams,
    tau_grid: Sequence[float],
    from_marginals: bool = False,
) -> float:
    """sum  n_l E[S(tau_l)] under joint or product marginals.

    ``n`` may be integer lot sizes or fractional expected counts (MF means);
    values are kept continuous (not floored).
    """
    n_l = [float(x) for x in n]
    L = len(n_l)
    grid = [float(t) for t in tau_grid]
    K = len(grid)
    if from_marginals:
        marg = np.asarray(joint_or_marginals, dtype=float)
    else:
        marg = marginals_from_joint(
            np.asarray(joint_or_marginals, dtype=float), L=L, K=K
        )
    total = 0.0
    for ell in range(L):
        e_s = 0.0
        for k in range(K):
            s = weibull_survival(grid[k], beta=params.beta, eta=params.eta_ref)
            e_s += float(marg[ell, k]) * s
        total += float(n_l[ell]) * e_s
    return float(total)

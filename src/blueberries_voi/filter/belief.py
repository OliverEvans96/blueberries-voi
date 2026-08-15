"""Controller-facing shelf belief: arrival-prior ages and B-state oracle (ADR 0106)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from blueberries_voi.filter.age_likelihood import survival_weighted_on_hand
from blueberries_voi.model import Cohort, ModelParams, weibull_survival

PendingOrders = Mapping[int, int]


@dataclass(frozen=True)
class ShelfBelief:
    """Frozen public shelf summary: lot counts, (L, K) age marginals, age grid."""

    lot_counts: list[float]
    age_marginals: list[list[float]]
    tau_grid: list[float]

    def to_export(self) -> dict[str, Any]:
        """JSON-friendly list/float payload (no numpy handles)."""
        return {
            "lot_counts": [float(x) for x in self.lot_counts],
            "age_marginals": [[float(x) for x in row] for row in self.age_marginals],
            "tau_grid": [float(t) for t in self.tau_grid],
        }

    @classmethod
    def from_export(cls, payload: Mapping[str, Any]) -> ShelfBelief:
        counts = [float(x) for x in payload["lot_counts"]]
        margs = [[float(x) for x in row] for row in payload["age_marginals"]]
        grid = [float(t) for t in payload["tau_grid"]]
        return cls(lot_counts=counts, age_marginals=margs, tau_grid=grid)


def _nearest_grid_index(age: float, tau_grid: Sequence[float]) -> int:
    return min(range(len(tau_grid)), key=lambda i: abs(float(tau_grid[i]) - age))


def _dirac_marginal(index: int, k: int) -> list[float]:
    row = [0.0] * k
    row[index] = 1.0
    return row


def _flat_prior_expected_survival(
    params: ModelParams, tau_grid: Sequence[float]
) -> float:
    if not tau_grid:
        return 0.0
    s = [
        weibull_survival(float(t), beta=params.beta, eta=params.eta_ref)
        for t in tau_grid
    ]
    return float(sum(s) / len(s))


def shelf_belief_from_rbpf(rbpf: Any) -> ShelfBelief:
    """Removed with production RBPF (T-121 Wave F); use Rust belief wire."""
    del rbpf
    msg = "shelf_belief_from_rbpf removed in T-121 Wave F (use Rust session belief)"
    raise RuntimeError(msg)


def shelf_belief_from_oracle(
    *,
    lot_counts: Sequence[int | float],
    ages: Sequence[float],
    tau_grid: Sequence[float],
) -> ShelfBelief:
    """Build ShelfBelief from B-state lot counts/ages (Dirac on nearest knot)."""
    counts = [float(x) for x in lot_counts]
    age_list = [float(a) for a in ages]
    grid = [float(t) for t in tau_grid]

    if len(counts) == 0:
        msg = "lot_counts must be non-empty"
        raise ValueError(msg)
    if len(counts) != len(age_list):
        msg = f"lot_counts length {len(counts)} != ages length {len(age_list)}"
        raise ValueError(msg)
    if len(grid) < 1:
        msg = "tau_grid must be non-empty"
        raise ValueError(msg)

    k = len(grid)
    margs = [_dirac_marginal(_nearest_grid_index(age, grid), k) for age in age_list]
    return ShelfBelief(lot_counts=counts, age_marginals=margs, tau_grid=grid)


def empty_shelf_belief(*, tau_grid: Sequence[float]) -> ShelfBelief:
    """Empty shelf with an explicit τ grid (call sites keep their own lengths)."""
    return ShelfBelief(
        lot_counts=[],
        age_marginals=[],
        tau_grid=[float(t) for t in tau_grid],
    )


def shelf_belief_from_cohorts_oracle(
    cohorts: Sequence[Cohort],
    *,
    empty_tau_grid: Sequence[float],
) -> ShelfBelief:
    """B-state ShelfBelief from live cohorts with dynamic even-τ pad (ADR 0092)."""
    live = [c for c in cohorts if c.n > 0]
    if not live:
        return empty_shelf_belief(tau_grid=empty_tau_grid)
    ages = [float(c.tau) for c in live]
    hi = max([*ages, 6.0]) + 2.0
    grid = [float(x) for x in range(0, int(hi) + 3, 2)]
    return shelf_belief_from_oracle(
        lot_counts=[int(c.n) for c in live],
        ages=ages,
        tau_grid=grid,
    )


def effective_inventory(
    belief: ShelfBelief,
    *,
    pending_orders: PendingOrders,
    params: ModelParams,
) -> float:
    """Survival-weighted on-hand (MF marginals) plus flat-prior pipeline term."""
    for qty in pending_orders.values():
        if int(qty) < 0:
            msg = "pending_orders quantities must be non-negative"
            raise ValueError(msg)

    n_on_hand = [float(x) for x in belief.lot_counts]
    marg = np.asarray(belief.age_marginals, dtype=float)
    on_hand = survival_weighted_on_hand(
        n_on_hand,
        marg,
        params=params,
        tau_grid=belief.tau_grid,
        from_marginals=True,
    )
    pipeline_w = _flat_prior_expected_survival(params, belief.tau_grid)
    pipeline = sum(float(qty) * pipeline_w for qty in pending_orders.values())
    return float(on_hand + pipeline)


__all__ = [
    "ShelfBelief",
    "effective_inventory",
    "empty_shelf_belief",
    "shelf_belief_from_cohorts_oracle",
    "shelf_belief_from_oracle",
    "shelf_belief_from_rbpf",
]

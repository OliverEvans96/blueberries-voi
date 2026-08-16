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


@dataclass(frozen=True)
class FreshShelfBelief:
    """Frozen f-native shelf summary: lot counts, (L, K) f marginals, f grid."""

    lot_counts: list[float]
    f_marginals: list[list[float]]
    f_grid: list[float]

    def to_export(self) -> dict[str, Any]:
        """JSON-friendly list/float payload (no numpy handles)."""
        flat_marginals = [float(p) for row in self.f_marginals for p in row]
        return {
            "lot_counts": [float(x) for x in self.lot_counts],
            "f_marginals": flat_marginals,
            "f_grid": [float(f) for f in self.f_grid],
            "L": len(self.lot_counts),
            "K": len(self.f_grid),
        }

    @classmethod
    def from_export(cls, payload: Mapping[str, Any]) -> FreshShelfBelief:
        counts = [float(x) for x in payload["lot_counts"]]
        grid = [float(f) for f in payload["f_grid"]]
        k = len(grid)
        flat = [float(x) for x in payload["f_marginals"]]
        margs = [flat[i * k : (i + 1) * k] for i in range(len(counts))]
        return cls(lot_counts=counts, f_marginals=margs, f_grid=grid)


def shelf_belief_from_f_oracle(
    *,
    lot_counts: Sequence[int | float],
    f_marginals: Sequence[Sequence[float]],
    f_grid: Sequence[float],
) -> FreshShelfBelief:
    """Build FreshShelfBelief from oracle lot counts and row f-marginals."""
    counts = [float(x) for x in lot_counts]
    grid = [float(f) for f in f_grid]
    margs = [[float(x) for x in row] for row in f_marginals]
    if len(counts) != len(margs):
        msg = f"lot_counts length {len(counts)} != f_marginals rows {len(margs)}"
        raise ValueError(msg)
    k = len(grid)
    if k < 1:
        msg = "f_grid must be non-empty"
        raise ValueError(msg)
    for row in margs:
        if len(row) != k:
            msg = f"each f_marginal row must have length K={k}"
            raise ValueError(msg)
    return FreshShelfBelief(lot_counts=counts, f_marginals=margs, f_grid=grid)


def empty_f_shelf_belief(*, f_grid: Sequence[float]) -> FreshShelfBelief:
    """Empty shelf with an explicit f grid."""
    return FreshShelfBelief(
        lot_counts=[],
        f_marginals=[],
        f_grid=[float(f) for f in f_grid],
    )


def effective_inventory_f_belief(
    belief: FreshShelfBelief,
    *,
    pending_orders: PendingOrders,
    f_pipeline_default: float,
) -> float:
    """E[f]-weighted on-hand from f-marginals plus pipeline term."""
    for qty in pending_orders.values():
        if int(qty) < 0:
            msg = "pending_orders quantities must be non-negative"
            raise ValueError(msg)

    k = len(belief.f_grid)
    on_hand = 0.0
    for ell, n_lot in enumerate(belief.lot_counts):
        e_f = sum(belief.f_marginals[ell][b] * belief.f_grid[b] for b in range(k))
        on_hand += float(n_lot) * e_f
    pipeline = sum(float(qty) * f_pipeline_default for qty in pending_orders.values())
    return float(on_hand + pipeline)


__all__ = [
    "FreshShelfBelief",
    "ShelfBelief",
    "effective_inventory",
    "effective_inventory_f_belief",
    "empty_f_shelf_belief",
    "empty_shelf_belief",
    "shelf_belief_from_cohorts_oracle",
    "shelf_belief_from_f_oracle",
    "shelf_belief_from_oracle",
]

"""Controller-facing shelf belief: f-native wire (ADR 0130 / 0131)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blueberries_voi.model import Cohort

PendingOrders = Mapping[int, int]

_DEFAULT_ETA_REF = 14.0


def _age_to_f(age: float, *, eta_ref: float) -> float:
    return max(0.0, 1.0 - float(age) / float(eta_ref))


def _f_to_age(freshness: float, *, eta_ref: float) -> float:
    return max(0.0, (1.0 - float(freshness)) * float(eta_ref))


def _nearest_grid_index(value: float, grid: Sequence[float]) -> int:
    return min(range(len(grid)), key=lambda i: abs(float(grid[i]) - value))


def _dirac_marginal(index: int, k: int) -> list[float]:
    row = [0.0] * k
    row[index] = 1.0
    return row


@dataclass(frozen=True)
class ShelfBelief:
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
    def from_export(cls, payload: Mapping[str, Any]) -> ShelfBelief:
        counts = [float(x) for x in payload["lot_counts"]]
        grid = [float(f) for f in payload["f_grid"]]
        k = len(grid)
        flat = [float(x) for x in payload["f_marginals"]]
        margs = [flat[i * k : (i + 1) * k] for i in range(len(counts))]
        return cls(lot_counts=counts, f_marginals=margs, f_grid=grid)


def shelf_belief_from_oracle(
    *,
    lot_counts: Sequence[int | float],
    f_marginals: Sequence[Sequence[float]],
    f_grid: Sequence[float],
) -> ShelfBelief:
    """Build ShelfBelief from oracle lot counts and row f-marginals."""
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
    return ShelfBelief(lot_counts=counts, f_marginals=margs, f_grid=grid)


def empty_shelf_belief(*, f_grid: Sequence[float]) -> ShelfBelief:
    """Empty shelf with an explicit f grid."""
    return ShelfBelief(
        lot_counts=[],
        f_marginals=[],
        f_grid=[float(f) for f in f_grid],
    )


def shelf_belief_from_cohorts_oracle(
    cohorts: Sequence[Cohort],
    *,
    empty_f_grid: Sequence[float],
    eta_ref: float = _DEFAULT_ETA_REF,
) -> ShelfBelief:
    """B-state ShelfBelief from live cohorts (Dirac on nearest f knot)."""
    live = [c for c in cohorts if c.n > 0]
    if not live:
        return empty_shelf_belief(f_grid=empty_f_grid)
    f_values = [_age_to_f(float(c.tau), eta_ref=eta_ref) for c in live]
    hi = max([*f_values, 0.5]) + 0.25
    grid = [round(x, 2) for x in [i / 4.0 for i in range(5)]]
    while grid[-1] < hi:
        grid.append(round(grid[-1] + 0.25, 2))
    k = len(grid)
    margs = [
        _dirac_marginal(_nearest_grid_index(f_val, grid), k) for f_val in f_values
    ]
    return ShelfBelief(
        lot_counts=[float(int(c.n)) for c in live],
        f_marginals=margs,
        f_grid=grid,
    )


def flatten_shelf_belief(belief: ShelfBelief) -> dict[str, Any]:
    """Flat f-native wire: lot_counts, f_marginals, f_grid, L, K."""
    return belief.to_export()


def unflatten_shelf_belief(payload: Mapping[str, Any]) -> ShelfBelief:
    """Rebuild ``ShelfBelief`` from a flat f-native wire buffer."""
    return ShelfBelief.from_export(payload)


def effective_inventory(
    belief: ShelfBelief,
    *,
    pending_orders: PendingOrders,
    f_pipeline_default: float = 1.0,
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


def mean_f_from_belief(belief: ShelfBelief, *, lot_index: int) -> float:
    """Expected freshness for one lot slot (helper for cohort bridge code)."""
    k = len(belief.f_grid)
    row = belief.f_marginals[lot_index]
    return float(sum(row[b] * belief.f_grid[b] for b in range(k)))


def cohort_tau_from_belief_lot(
    belief: ShelfBelief, *, lot_index: int, eta_ref: float = _DEFAULT_ETA_REF
) -> float:
    """Map belief lot E[f] to cohort τ for legacy day_step bridges."""
    return _f_to_age(mean_f_from_belief(belief, lot_index=lot_index), eta_ref=eta_ref)


__all__ = [
    "ShelfBelief",
    "cohort_tau_from_belief_lot",
    "effective_inventory",
    "empty_shelf_belief",
    "flatten_shelf_belief",
    "mean_f_from_belief",
    "shelf_belief_from_cohorts_oracle",
    "shelf_belief_from_oracle",
    "unflatten_shelf_belief",
]

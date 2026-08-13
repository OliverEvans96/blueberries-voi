"""Flat belief wire buffers at the EngineSession boundary (ADR 0098)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from blueberries_voi.filter.belief import ShelfBelief
from blueberries_voi.filter.types import age_grid

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

Snapshot = dict[str, Any]
DayDelta = dict[str, Any]
FlatBelief = dict[str, Any]


def flatten_shelf_belief(belief: ShelfBelief) -> FlatBelief:
    """Encode nested ShelfBelief as flat L / L*K / K wire buffers."""
    lot_counts = [float(x) for x in belief.lot_counts]
    tau = [float(t) for t in belief.tau_grid]
    l_dim = len(lot_counts)
    k_dim = len(tau)
    flat: list[float] = []
    for row in belief.age_marginals:
        flat.extend(float(x) for x in row)
    if len(flat) != l_dim * k_dim:
        msg = f"age_marginals flatten length {len(flat)} != L*K={l_dim * k_dim}"
        raise ValueError(msg)
    return {
        "lot_counts": lot_counts,
        "age_marginals": flat,
        "tau_grid": tau,
        "L": l_dim,
        "K": k_dim,
    }


def empty_flat_belief(*, L: int, K: int) -> FlatBelief:
    """Prior empty shelf with configured L/K (all-zero counts, flat age rows)."""
    if L < 0 or K < 0:
        msg = f"L and K must be non-negative, got L={L}, K={K}"
        raise ValueError(msg)
    if K == 0 and L > 0:
        msg = "K must be >= 1 when L > 0"
        raise ValueError(msg)
    if K >= 2:
        grid = [float(t) for t in age_grid(K)]
    elif K == 1:
        grid = [0.0]
    else:
        grid = []
    lot_counts = [0.0] * L
    if L == 0:
        return {
            "lot_counts": [],
            "age_marginals": [],
            "tau_grid": grid,
            "L": 0,
            "K": K,
        }
    uniform = [1.0 / float(K)] * K
    flat = uniform * L
    return {
        "lot_counts": lot_counts,
        "age_marginals": flat,
        "tau_grid": grid,
        "L": L,
        "K": K,
    }


def shelf_belief_from_flat(payload: Mapping[str, Any]) -> ShelfBelief:
    """Rebuild nested ShelfBelief from a flat wire buffer."""
    counts = [float(x) for x in payload["lot_counts"]]
    flat = [float(x) for x in payload["age_marginals"]]
    grid = [float(t) for t in payload["tau_grid"]]
    l_dim = int(payload["L"])
    k_dim = int(payload["K"])
    if len(counts) != l_dim or len(flat) != l_dim * k_dim or len(grid) != k_dim:
        msg = "flat belief dimensions inconsistent with L/K"
        raise ValueError(msg)
    rows: list[list[float]] = [flat[i * k_dim : (i + 1) * k_dim] for i in range(l_dim)]
    return ShelfBelief(lot_counts=counts, age_marginals=rows, tau_grid=grid)


def live_lots_payload(cohorts: Sequence[Any]) -> list[dict[str, Any]]:
    """JSON-friendly live lot snapshot."""
    out: list[dict[str, Any]] = []
    for c in cohorts:
        n = int(getattr(c, "n", 0))
        if n <= 0:
            continue
        out.append(
            {
                "lot_id": int(getattr(c, "lot_id", 0)),
                "n": n,
                "tau": float(getattr(c, "tau", 0.0)),
            }
        )
    return out


def pipeline_payload(pending: Mapping[int, int]) -> list[dict[str, int]]:
    """JSON-friendly pending arrival pipeline (arrival_day, qty)."""
    return [
        {"arrival_day": int(day), "qty": int(qty)}
        for day, qty in sorted(pending.items())
        if int(qty) != 0
    ]


__all__ = [
    "DayDelta",
    "FlatBelief",
    "Snapshot",
    "empty_flat_belief",
    "flatten_shelf_belief",
    "live_lots_payload",
    "pipeline_payload",
    "shelf_belief_from_flat",
]

"""Flat belief wire buffers at the EngineSession boundary (ADR 0100)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from blueberries_voi.filter.belief import FreshShelfBelief

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

Snapshot = dict[str, Any]
DayDelta = dict[str, Any]
FlatBelief = dict[str, Any]


def f_grid_k(k: int) -> list[float]:
    """Freshness bin centers in [0, 1] for wire dimension K (Rust f_grid_k)."""
    if k < 0:
        msg = f"K must be non-negative, got {k}"
        raise ValueError(msg)
    if k == 0:
        return []
    if k == 1:
        return [0.0]
    return [float(i) / float(k - 1) for i in range(k)]


def flatten_shelf_belief(belief: FreshShelfBelief) -> FlatBelief:
    """Encode nested FreshShelfBelief as flat L / L*K / K f-native wire buffers."""
    return belief.to_export()


def empty_flat_belief(*, L: int, K: int) -> FlatBelief:
    """Prior empty shelf with configured L/K (all-zero counts, flat uniform f rows)."""
    if L < 0 or K < 0:
        msg = f"L and K must be non-negative, got L={L}, K={K}"
        raise ValueError(msg)
    if K == 0 and L > 0:
        msg = "K must be >= 1 when L > 0"
        raise ValueError(msg)
    grid = f_grid_k(K)
    lot_counts = [0.0] * L
    if L == 0:
        return {
            "lot_counts": [],
            "f_marginals": [],
            "f_grid": grid,
            "L": 0,
            "K": K,
        }
    uniform = [1.0 / float(K)] * K
    flat = uniform * L
    return {
        "lot_counts": lot_counts,
        "f_marginals": flat,
        "f_grid": grid,
        "L": L,
        "K": K,
    }


def shelf_belief_from_flat(payload: Mapping[str, Any]) -> FreshShelfBelief:
    """Rebuild nested FreshShelfBelief from a flat f-native wire buffer."""
    return FreshShelfBelief.from_export(payload)


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
    "f_grid_k",
    "flatten_shelf_belief",
    "live_lots_payload",
    "pipeline_payload",
    "shelf_belief_from_flat",
]

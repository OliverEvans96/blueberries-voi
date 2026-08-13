"""CTL-04 survival-weighted terminal salvage helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from blueberries_voi.model import ModelParams, weibull_survival

__all__ = [
    "terminal_salvage_value",
    "w_long_oldest_first",
]


def _lot_n(lot: Any) -> float:
    if isinstance(lot, Mapping):
        return float(lot["n"])
    return float(lot.n)


def _lot_tau(lot: Any) -> float:
    if isinstance(lot, Mapping):
        return float(lot["tau"])
    return float(lot.tau)


def w_long_oldest_first(
    lots: Sequence[Mapping[str, Any]] | Sequence[Any],
    *,
    params: ModelParams,
) -> list[float]:
    """Survival weights for lots in oldest-first queue order (ADR 0061).

    Lots are interpreted in the given order as the oldest-first allocation
    queue. ``w_long(τ)`` is Weibull survival at the lot's effective age so
    newer / fresher stock (higher S) contributes more salvage value.
    """
    weights: list[float] = []
    for lot in lots:
        tau = float(_lot_tau(lot))
        weights.append(weibull_survival(tau, beta=params.beta, eta=params.eta_ref))
    return weights


def terminal_salvage_value(
    lots: Sequence[Mapping[str, Any]] | Sequence[Any],
    *,
    margin: float,
    params: ModelParams,
) -> float:
    """Terminal salvage V_T = m * sum_l w_long(tau_l) * n_l (ADR 0061 / CTL-04)."""
    if not lots:
        return 0.0
    weights = w_long_oldest_first(lots, params=params)
    total = 0.0
    for w, lot in zip(weights, lots, strict=True):
        total += float(w) * float(_lot_n(lot))
    return float(margin) * total

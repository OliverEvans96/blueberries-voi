"""Shared Policy.order dual-dispatch (day-first vs belief-first).

Public controller policies keep their own signatures (T-024 day-first Protocol
vs T-028 belief-first). Drivers call ``invoke_order`` so ``inspect.signature``
dispatch lives in one place (ADR 0118 / T-102 Wave B3).
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


class SupportsOrder(Protocol):
    """Structural surface for dual-dispatch ``order`` callables."""

    def order(self, *args: Any, **kwargs: Any) -> int: ...


def _empty_shelf_belief() -> object:
    """Minimal ShelfBelief when belief-first policies receive ``None``."""
    from blueberries_voi.filter.belief import ShelfBelief

    return ShelfBelief(
        lot_counts=[],
        age_marginals=[],
        tau_grid=[0.0, 2.0, 4.0, 6.0],
    )


def invoke_order(
    policy: SupportsOrder,
    day: int,
    belief: object | None,
    pending_orders: Mapping[int, int],
) -> int:
    """Dispatch day-first (T-024) or belief-first (T-028) policy surfaces."""
    sig = inspect.signature(policy.order)
    names = list(sig.parameters)
    if names and names[0] == "day":
        return int(policy.order(day, belief, pending_orders=pending_orders))
    shelf = belief if belief is not None else _empty_shelf_belief()
    kwargs: dict[str, object] = {"pending_orders": pending_orders}
    if "day" in sig.parameters:
        kwargs["day"] = day
    return int(policy.order(shelf, **kwargs))


__all__ = [
    "SupportsOrder",
    "invoke_order",
]

"""Case-size rounding, constant-order policy, and dual-dispatch ``invoke_order``.

Rounding mode for ``case_round``: map ``x`` to the **nearest** multiple of
``case_size``. Halfway ties use **half away from zero** (for non-negative
``x``, toward +∞ / the larger multiple). Default ``case_size=8`` matches
``ModelParams.case_size``.

Public controller policies keep their own signatures (T-024 day-first Protocol
vs T-028 belief-first). Drivers call ``invoke_order`` so ``inspect.signature``
dispatch lives in one place (ADR 0118 / T-102 Wave B3).
"""

from __future__ import annotations

import inspect
import math
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping


def case_round(x: float, case_size: int = 8) -> int:
    """Round ``x`` to the nearest non-negative multiple of ``case_size``.

    Ties (exactly halfway between two multiples) round half away from zero.
    """
    if case_size <= 0:
        raise ValueError(f"case_size must be positive, got {case_size}")
    if x < 0:
        raise ValueError(f"x must be non-negative, got {x}")
    # For non-negative n, floor(n + 0.5) is half-away-from-zero.
    n = x / case_size
    return int(math.floor(n + 0.5) * case_size)


class ConstantOrderPolicy:
    """Policy that always orders a fixed case-rounded quantity."""

    def __init__(self, q: int, *, case_size: int = 8) -> None:
        self._q = case_round(float(q), case_size)

    def order(
        self,
        belief: Any,
        *,
        day: int = 0,
        pending_orders: tuple[int, ...] = (),
    ) -> int:
        del belief, day, pending_orders
        return self._q


class SupportsOrder(Protocol):
    """Structural surface for dual-dispatch ``order`` callables."""

    def order(self, *args: Any, **kwargs: Any) -> int: ...


def _empty_shelf_belief() -> object:
    """Minimal ShelfBelief when belief-first policies receive ``None``."""
    from blueberries_voi.filter.belief import ShelfBelief

    return ShelfBelief(
        lot_counts=[],
        f_marginals=[],
        f_grid=[0.0, 2.0, 4.0, 6.0],
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
    "ConstantOrderPolicy",
    "SupportsOrder",
    "case_round",
    "invoke_order",
]

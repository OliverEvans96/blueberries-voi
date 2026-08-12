"""Case-size rounding and a constant-order policy primitive.

Rounding mode for ``case_round``: map ``x`` to the **nearest** multiple of
``case_size``. Halfway ties use **half away from zero** (for non-negative
``x``, toward +∞ / the larger multiple). Default ``case_size=8`` matches
``ModelParams.case_size``.
"""

from __future__ import annotations

import math
from typing import Any


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

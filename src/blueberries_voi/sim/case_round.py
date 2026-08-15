"""Case-size rounding helper (retained for sim/viz after Wave F).

Production policy compute lives in ``voi_core`` (ADR 0127). This module keeps the
frozen nearest-multiple rounding contract from deleted ``controller/ordering.py``.
"""

from __future__ import annotations

import math


def case_round(x: float, case_size: int = 8) -> int:
    """Round ``x`` to the nearest non-negative multiple of ``case_size``.

    Ties (exactly halfway between two multiples) round half away from zero.
    """
    if case_size <= 0:
        raise ValueError(f"case_size must be positive, got {case_size}")
    if x < 0:
        raise ValueError(f"x must be non-negative, got {x}")
    n = x / case_size
    return int(math.floor(n + 0.5) * case_size)


__all__ = ["case_round"]

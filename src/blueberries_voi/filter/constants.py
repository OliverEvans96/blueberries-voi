"""Filter production numerics (types/constants only after Wave F)."""

from __future__ import annotations

PRODUCTION_BACKEND: str = "counts_only"
PRODUCTION_K: int = 8
PRODUCTION_N: int = 2000
PRODUCTION_ESS_FRACTION: float = 0.5
PRODUCTION_L: int = 3

__all__ = [
    "PRODUCTION_BACKEND",
    "PRODUCTION_ESS_FRACTION",
    "PRODUCTION_K",
    "PRODUCTION_L",
    "PRODUCTION_N",
]

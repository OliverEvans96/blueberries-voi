"""Controller preset constants (retained after Wave F policy compute removal)."""

from __future__ import annotations

DEFAULT_ROLLOUT_HORIZONS: tuple[int, ...] = (7, 14, 21, 28)
DEFAULT_ROLLOUT_H: int = 28
DEFAULT_N_ROLLOUT_PATHS: int = 8
DEFAULT_CANDIDATE_CASE_RADIUS: int = 2

__all__ = [
    "DEFAULT_CANDIDATE_CASE_RADIUS",
    "DEFAULT_N_ROLLOUT_PATHS",
    "DEFAULT_ROLLOUT_H",
    "DEFAULT_ROLLOUT_HORIZONS",
]

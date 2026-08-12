"""Filter types and P1 observation contract."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from blueberries_voi.model import ModelParams, day_step

# Memory budget: K^L * N floats (FIL-13 / T-005).
MAX_JOINT_FLOATS: float = 5.0e7

AGE_GRID_LO: float = 0.0
AGE_GRID_HI: float = 8.0


@dataclass(frozen=True)
class P1Obs:
    sales_total: int
    waste_total: int
    arrivals: int


@dataclass
class FilterSummary:
    ess: float
    mean_L: float
    log_lik: float


def age_grid(K: int) -> np.ndarray:
    if K < 2:
        msg = "K must be >= 2"
        raise ValueError(msg)
    return np.linspace(AGE_GRID_LO, AGE_GRID_HI, K)


def joint_state_count(K: int, L: int, N: int) -> float:
    return float(K**L) * float(N)


def guard_joint_memory(K: int, L: int, N: int) -> None:
    n = joint_state_count(K, L, N)
    if n > MAX_JOINT_FLOATS:
        msg = (
            f"Joint age posterior budget exceeded: "
            f"K^L*N={n:.3e} > {MAX_JOINT_FLOATS:.3e} "
            f"(K={K}, L={L}, N={N}). Escalate FIL-13 - do not silently truncate L."
        )
        raise MemoryError(msg)


__all__ = [
    "AGE_GRID_HI",
    "AGE_GRID_LO",
    "MAX_JOINT_FLOATS",
    "FilterSummary",
    "ModelParams",
    "P1Obs",
    "age_grid",
    "day_step",
    "guard_joint_memory",
    "joint_state_count",
]

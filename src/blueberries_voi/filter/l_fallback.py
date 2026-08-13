"""Production backend selection: always counts_only (ADR 0105).

``joint_state_count`` is still reported on ``BackendChoice`` for diagnostics;
it is not a production gate (no K^L·N → sliding_window fallback).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from blueberries_voi.filter.types import joint_state_count

BackendName = Literal["counts_only"]


@dataclass(frozen=True)
class BackendChoice:
    """Structured record of which production backend was selected."""

    backend: BackendName
    K: int
    L: int
    N: int
    joint_floats: float
    reason: str


def choose_backend(K: int, L: int, N: int) -> BackendChoice:
    """Always select ``counts_only``; never truncate ``L`` (ADR 0105).

    ``joint_floats`` remains diagnostic only and does not gate production.
    """
    floats = joint_state_count(K, L, N)
    return BackendChoice(
        backend="counts_only",
        K=K,
        L=L,
        N=N,
        joint_floats=floats,
        reason=(
            f"production backend counts_only (ADR 0105); "
            f"K^L*N={floats:.3e} diagnostic only "
            f"(K={K}, L={L}, N={N}); L preserved, no joint gate"
        ),
    )


__all__ = [
    "BackendChoice",
    "BackendName",
    "choose_backend",
]

"""Dynamic L + joint→sliding_window fallback (ADR 0089 / T-015 / FIL-13)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from blueberries_voi.filter.types import MAX_JOINT_FLOATS, joint_state_count

BackendName = Literal["full_joint", "sliding_window"]


@dataclass(frozen=True)
class BackendChoice:
    """Structured record of which age-posterior backend was selected."""

    backend: BackendName
    K: int
    L: int
    N: int
    joint_floats: float
    reason: str


def choose_backend(K: int, L: int, N: int) -> BackendChoice:
    """Select ``full_joint`` while under budget; else ``sliding_window``.

    Never truncates ``L`` to fit the joint float budget (FIL-13).
    """
    floats = joint_state_count(K, L, N)
    if floats <= MAX_JOINT_FLOATS:
        return BackendChoice(
            backend="full_joint",
            K=K,
            L=L,
            N=N,
            joint_floats=floats,
            reason=(
                f"within joint budget: K^L*N={floats:.3e} <= {MAX_JOINT_FLOATS:.3e} "
                f"(K={K}, L={L}, N={N}); keep full_joint"
            ),
        )
    return BackendChoice(
        backend="sliding_window",
        K=K,
        L=L,
        N=N,
        joint_floats=floats,
        reason=(
            f"joint budget exceeded: K^L*N={floats:.3e} > {MAX_JOINT_FLOATS:.3e} "
            f"(K={K}, L={L}, N={N}); fallback to sliding_window (FIL-13)"
        ),
    )


__all__ = [
    "BackendChoice",
    "BackendName",
    "choose_backend",
]

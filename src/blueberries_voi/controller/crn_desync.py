"""ENG-04 CRN desync detector (peeled from controller.rollout)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from blueberries_voi.rng import spawn_rng

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "CrnDesyncResult",
    "detect_crn_desync",
]


@dataclass(frozen=True)
class CrnDesyncResult:
    """ENG-04 CRN desync detector outcome."""

    ok: bool
    status: str


def detect_crn_desync(
    *,
    address_a: Mapping[str, Any],
    address_b: Mapping[str, Any],
    n_draws: int = 32,
) -> CrnDesyncResult:
    """Compare two SIM-05 stream addresses; ``ok`` iff draw sequences match."""
    if n_draws <= 0:
        msg = f"n_draws must be positive, got {n_draws}"
        raise ValueError(msg)
    a = spawn_rng(
        int(address_a["root_seed"]),
        run_id=address_a["run_id"],
        day=int(address_a["day"]),
        stream=str(address_a["stream"]),
    )
    b = spawn_rng(
        int(address_b["root_seed"]),
        run_id=address_b["run_id"],
        day=int(address_b["day"]),
        stream=str(address_b["stream"]),
    )
    draws_a = a.random(int(n_draws))
    draws_b = b.random(int(n_draws))
    if np.array_equal(draws_a, draws_b):
        return CrnDesyncResult(ok=True, status="ok")
    return CrnDesyncResult(ok=False, status="desync")

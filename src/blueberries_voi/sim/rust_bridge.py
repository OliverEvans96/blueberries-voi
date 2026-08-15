"""Rust-backed day_step shim for bakeoff / research sim paths (T-121 Wave F).

Production ``EngineSession`` and ``run_voi_crn_cell`` delegate directly to
``voi_core``. This module keeps open-loop / M2 research callers on the Rust kernel
without retaining ``model/day_step.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.backend import rust_available, warn_fallback_once
from blueberries_voi.model.params import Cohort, DayStepResult, ModelParams

if TYPE_CHECKING:
    from collections.abc import Sequence


def day_step(
    cohorts: Sequence[Cohort],
    *,
    params: ModelParams,
    demand: int | None = None,
    delivery: Cohort | None = None,
    rng_demand: np.random.Generator | None = None,
    rng_alloc: np.random.Generator | None = None,
    rng_spoil: np.random.Generator | None = None,
    event_log: list[str] | None = None,
    day: int | None = None,
) -> DayStepResult:
    """Apply one MOD-12 day via ``blueberries_voi._core.day_step_injected``."""
    del params, rng_demand, event_log, day
    warn_fallback_once()
    if not rust_available() or demand is None:
        msg = "sim.rust_bridge.day_step requires rust backend and fixed demand"
        raise RuntimeError(msg)
    from blueberries_voi.backend import rust_core

    assert rust_core is not None
    live = [Cohort(n=c.n, tau=c.tau, lot_id=c.lot_id) for c in cohorts if c.n > 0]
    seed = 0
    if rng_alloc is not None:
        seed = int(rng_alloc.integers(0, 2**31 - 1))
    elif rng_spoil is not None:
        seed = int(rng_spoil.integers(0, 2**31 - 1))
    dn = int(delivery.n) if delivery is not None else 0
    dtau = float(delivery.tau) if delivery is not None else 0.0
    dlot = int(delivery.lot_id) if delivery is not None else 0
    counts, taus, lot_ids, dem, sales_t, waste_t = rust_core.day_step_injected(
        [int(c.n) for c in live],
        [float(c.tau) for c in live],
        [int(c.lot_id) for c in live],
        int(demand),
        dn,
        dtau,
        dlot,
        seed,
    )
    out_c = [
        Cohort(n=int(n), tau=float(t), lot_id=int(i))
        for n, t, i in zip(counts, taus, lot_ids, strict=True)
    ]
    return DayStepResult(
        cohorts=out_c,
        demand=int(dem),
        sales_total=int(sales_t),
        sales_by_cohort=np.zeros(0, dtype=int),
        waste_total=int(waste_t),
        waste_by_cohort=np.zeros(0, dtype=int),
    )


__all__ = ["day_step"]

"""Rust-backed day_step shim for bakeoff / research sim paths (T-121 Wave F).

Production ``EngineSession`` and ``run_voi_crn_cell`` delegate directly to
``voi_core``. This module keeps open-loop / M2 research callers on the Rust kernel
when ``day_step_injected`` is present; otherwise falls back to the cohort Python
kernel for notebooks / alpha-tune until the injected shim is restored.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.backend import rust_available, warn_fallback_once
from blueberries_voi.model.constitutive import (
    allocate_sales,
    death_prob_survival_ratio,
    draw_demand,
    picking_weights,
    q10_age_increment,
)
from blueberries_voi.model.params import Cohort, DayStepResult, ModelParams

if TYPE_CHECKING:
    from collections.abc import Sequence


def _rust_day_step_injected(
    cohorts: Sequence[Cohort],
    *,
    params: ModelParams,
    demand: int,
    delivery: Cohort | None,
    rng_alloc: np.random.Generator | None,
    rng_spoil: np.random.Generator | None,
) -> DayStepResult:
    warn_fallback_once()
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


def _python_day_step(
    cohorts: Sequence[Cohort],
    *,
    params: ModelParams,
    demand: int | None,
    delivery: Cohort | None,
    rng_demand: np.random.Generator | None,
    rng_alloc: np.random.Generator | None,
    rng_spoil: np.random.Generator | None,
    day: int | None,
) -> DayStepResult:
    """Cohort MOD-12 day: age → demand → allocate → spoil → deliver."""
    live = [Cohort(n=c.n, tau=c.tau, lot_id=c.lot_id) for c in cohorts if c.n > 0]

    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    for c in live:
        c.tau += dtau

    if demand is None:
        if rng_demand is None:
            msg = "demand or rng_demand required"
            raise ValueError(msg)
        demand_draw = draw_demand(rng_demand, params, day=day)
    else:
        demand_draw = int(demand)

    if live:
        taus = [c.tau for c in live]
        counts = [c.n for c in live]
        weights = picking_weights(
            taus,
            sigma=params.sigma,
            beta=params.beta,
            eta=params.eta_ref,
            uniform=params.uniform_picking,
        )
        if rng_alloc is None:
            msg = "rng_alloc required when cohorts are live"
            raise ValueError(msg)
        sales_by = allocate_sales(counts, demand_draw, weights, rng_alloc)
        for i, c in enumerate(live):
            c.n -= int(sales_by[i])
    else:
        sales_by = np.zeros(0, dtype=int)
    sales_total = int(sales_by.sum())

    waste_by = np.zeros(len(live), dtype=int)
    if live:
        if rng_spoil is None:
            msg = "rng_spoil required when cohorts are live"
            raise ValueError(msg)
        for i, c in enumerate(live):
            if c.n <= 0:
                continue
            p_die = death_prob_survival_ratio(
                c.tau,
                dtau,
                beta=params.beta,
                eta=params.eta_ref,
            )
            waste = int(rng_spoil.binomial(c.n, p_die))
            waste_by[i] = waste
            c.n -= waste
    waste_total = int(waste_by.sum())

    live = [c for c in live if c.n > 0]

    if delivery is not None and delivery.n > 0:
        live.append(Cohort(n=delivery.n, tau=delivery.tau, lot_id=delivery.lot_id))

    return DayStepResult(
        cohorts=live,
        demand=demand_draw,
        sales_total=sales_total,
        sales_by_cohort=sales_by,
        waste_total=waste_total,
        waste_by_cohort=waste_by,
    )


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
    """Apply one MOD-12 day (Rust injected shim when available, else Python cohort)."""
    del event_log
    if rust_available() and demand is None and rng_demand is None:
        msg = "sim.rust_bridge.day_step requires rust backend and fixed demand"
        raise RuntimeError(msg)
    if (
        demand is not None
        and rust_available()
        and rust_core is not None
        and getattr(rust_core, "day_step_injected", None) is not None
    ):
        return _rust_day_step_injected(
            cohorts,
            params=params,
            demand=demand,
            delivery=delivery,
            rng_alloc=rng_alloc,
            rng_spoil=rng_spoil,
        )
    return _python_day_step(
        cohorts,
        params=params,
        demand=demand,
        delivery=delivery,
        rng_demand=rng_demand,
        rng_alloc=rng_alloc,
        rng_spoil=rng_spoil,
        day=day,
    )


# Late import for getattr guard above (rust_core may be None).
from blueberries_voi.backend import rust_core  # noqa: E402

__all__ = ["day_step"]

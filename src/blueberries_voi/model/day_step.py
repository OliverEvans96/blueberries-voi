"""Shared MOD-12 day transition."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.model.params import Cohort, DayStepResult, ModelParams
from blueberries_voi.model.physics import (
    allocate_sales,
    death_prob_survival_ratio,
    draw_demand,
    picking_weights,
    q10_age_increment,
)

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
    """Apply MOD-12 events: age → demand → allocate → spoil → deliver."""
    live = [Cohort(n=c.n, tau=c.tau, lot_id=c.lot_id) for c in cohorts if c.n > 0]

    # 1. Age
    if event_log is not None:
        event_log.append("age")
    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    for c in live:
        c.tau += dtau

    # 2. Demand
    if event_log is not None:
        event_log.append("demand")
    if demand is None:
        if rng_demand is None:
            msg = "demand or rng_demand required"
            raise ValueError(msg)
        demand_draw = draw_demand(rng_demand, params, day=day)
    else:
        demand_draw = int(demand)

    # 3. Allocate sales
    if event_log is not None:
        event_log.append("allocate")
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

    # 4. Spoil survivors
    if event_log is not None:
        event_log.append("spoil")
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

    # Drop extinct cohorts (FIL-14=A: n==0 only).
    live = [c for c in live if c.n > 0]

    # 5. Deliver
    if event_log is not None:
        event_log.append("deliver")
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


__all__ = [
    "day_step",
]

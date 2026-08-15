"""Shared closed-loop day driver for EngineSession (order → DayDelta).

Minimal ``Day`` chart fields emitted on each tick (T-043; T-045 freezes goldens):

- ``day``: episode day index just completed
- ``order_qty``: units ordered this tick (after case rounding)
- ``arrivals``: units arriving today
- ``sales_total``, ``waste_total``, ``demand``: day_step outcomes
- ``L``: live lot count after the day

No matplotlib / pyarrow imports on this path. Shipments must be injected.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import numpy as np

from blueberries_voi.filter.belief import ShelfBelief, shelf_belief_from_rbpf
from blueberries_voi.filter.types import mask_for, rich_obs_from_day_log
from blueberries_voi.model import Cohort, ModelParams, day_step
from blueberries_voi.rng import (
    STREAM_ALLOC,
    STREAM_ARRIVAL_SENSOR,
    STREAM_ARRIVAL_SHIP,
    STREAM_DEMAND,
    STREAM_FILTER_RESAMPLE,
    STREAM_SPOIL,
    spawn_rng,
)
from blueberries_voi.sim.day_tick import (
    enqueue_pending_order,
    nonzero_lot_maps,
    pack_date_from_epoch,
    pop_arrival_units,
    pre_live_lot_ids,
)
from blueberries_voi.sim.open_loop import generate_arrival_age
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule
from blueberries_voi.simulator.belief import (
    flatten_shelf_belief,
    live_lots_payload,
    pipeline_payload,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping, Sequence
    from datetime import date

    from blueberries_voi.filter.rbpf import RBPF
    from blueberries_voi.filter.types import ScenarioId
    from blueberries_voi.model.abdella import ShipmentTrace
    from blueberries_voi.simulator.belief import DayDelta, FlatBelief


def _case_round_ceil(order_qty: int, case_size: int) -> int:
    """Ceil order quantity to whole cases; zero stays zero (closed-loop convention)."""
    qty = max(0, int(order_qty))
    if qty <= 0:
        return 0
    cases = int(np.ceil(qty / case_size))
    return cases * case_size


@dataclass
class DayDriverState:
    """Mutable physics + filter state advanced by ``advance_day``."""

    cohorts: list[Cohort]
    pending: dict[int, int]
    next_lot_id: int
    episode_day: int
    rbpf: RBPF | None = None


@dataclass(frozen=True)
class DayAdvanceResult:
    """One closed-loop tick: DayDelta pieces plus updated driver state."""

    day: dict[str, Any]
    belief: FlatBelief | None
    live_lots: list[dict[str, Any]]
    pipeline: list[dict[str, int]]
    state: DayDriverState


def advance_day(
    state: DayDriverState,
    order_qty: int,
    *,
    shipments: Sequence[ShipmentTrace],
    params: ModelParams,
    root_seed: int,
    run_id: str | int = "session",
    lead_time: int = 1,
    spread_scale: float = 1.0,
    enable_filter: bool = True,
    schedule: OrderSchedule | None = None,
    obs_scenario: ScenarioId | str = "P1",
) -> DayAdvanceResult:
    """Run order → pending/arrival → ``day_step`` → obs → optional RBPF → belief.

    Shared by ``EngineSession.step`` / ``act`` so hosts share one physics path.
    Orders are gated by ``schedule`` (default ``DEFAULT_ORDER_SCHEDULE``): on
    non-order days applied ``order_qty`` is coerced to 0.
    Filter observations use ``mask_for(obs_scenario)`` + ``rich_obs_from_day_log``
    on a DayLog-shaped richest day (same mapping as ``sim.episode``).
    """
    if not isinstance(order_qty, (int, np.integer)) or isinstance(order_qty, bool):
        msg = f"order_qty must be an int, got {type(order_qty)!r}"
        raise TypeError(msg)

    day = int(state.episode_day)
    pending: dict[int, int] = dict(state.pending)
    cohorts = list(state.cohorts)
    next_lot_id = int(state.next_lot_id)
    rbpf = state.rbpf
    sched = DEFAULT_ORDER_SCHEDULE if schedule is None else schedule

    # Ceil (not nearest): intentional fork vs closed-loop episode ``case_round``.
    order_units = _case_round_ceil(int(order_qty), params.case_size)
    if not sched.can_order(day):
        order_units = 0
    enqueue_pending_order(pending, day, lead_time, order_units)

    arrival_units = pop_arrival_units(pending, day)
    delivery: Cohort | None = None
    age_at_receipt: float | None = None
    pack_date: date | None = None
    if arrival_units > 0:
        if not shipments:
            msg = "shipments must be non-empty"
            raise ValueError(msg)
        # Bit-identical to former local ``_arrival_age``: same streams + args as
        # ``generate_arrival_age`` (SHIP/SENSOR spawn then bootstrap + spread).
        rng_ship = spawn_rng(
            root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SHIP
        )
        rng_sensor = spawn_rng(
            root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SENSOR
        )
        tau_in = generate_arrival_age(
            rng_ship,
            rng_sensor,
            list(shipments),
            params,
            spread_scale=spread_scale,
        )
        delivery = Cohort(n=arrival_units, tau=tau_in, lot_id=next_lot_id)
        next_lot_id += 1
        age_at_receipt = float(tau_in)
        pack_date = pack_date_from_epoch(day, age_at_receipt)

    pre_live_ids = pre_live_lot_ids(cohorts)
    rng_d = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_DEMAND)
    rng_a = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_ALLOC)
    rng_s = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_SPOIL)
    result = day_step(
        cohorts,
        day=day,
        params=params,
        delivery=delivery,
        rng_demand=rng_d,
        rng_alloc=rng_a,
        rng_spoil=rng_s,
    )
    cohorts = result.cohorts

    sales_by_lot, waste_by_lot = nonzero_lot_maps(
        pre_live_ids, result.sales_by_cohort, result.waste_by_cohort
    )

    rich_day = SimpleNamespace(
        day=day,
        order_qty=order_units,
        arrivals=int(arrival_units),
        sales_total=int(result.sales_total),
        waste_total=int(result.waste_total),
        demand=int(result.demand),
        L=len([c for c in cohorts if c.n > 0]),
        sales_by_lot=sales_by_lot,
        waste_by_lot=waste_by_lot,
        age_at_receipt=age_at_receipt,
        pack_date=pack_date,
        lots=cohorts,
    )

    belief_flat: FlatBelief | None = None
    if enable_filter and rbpf is not None:
        obs = rich_obs_from_day_log(rich_day, mask_for(obs_scenario))
        step_rng = spawn_rng(
            int(root_seed),
            run_id=run_id,
            day=day,
            stream=STREAM_FILTER_RESAMPLE,
        )
        rbpf.step(obs, step_rng)
        shelf: ShelfBelief = shelf_belief_from_rbpf(rbpf)
        belief_flat = flatten_shelf_belief(shelf)

    day_obj: dict[str, Any] = {
        "day": day,
        "order_qty": order_units,
        "arrivals": int(arrival_units),
        "sales_total": int(result.sales_total),
        "waste_total": int(result.waste_total),
        "demand": int(result.demand),
        "L": len([c for c in cohorts if c.n > 0]),
        "sales_by_lot": dict(sales_by_lot),
        "waste_by_lot": dict(waste_by_lot),
        "age_at_receipt": age_at_receipt,
        "pack_date": pack_date.isoformat() if pack_date is not None else None,
        "_rich": rich_day,
    }

    new_state = DayDriverState(
        cohorts=cohorts,
        pending=pending,
        next_lot_id=next_lot_id,
        episode_day=day + 1,
        rbpf=rbpf,
    )
    return DayAdvanceResult(
        day=day_obj,
        belief=belief_flat,
        live_lots=live_lots_payload(cohorts),
        pipeline=pipeline_payload(pending),
        state=new_state,
    )


def build_day_delta(
    *,
    seq: int,
    episode_day: int,
    result: DayAdvanceResult,
    drop_oldest: bool = False,
) -> DayDelta:
    """Frame a DayAdvanceResult as an ADR 0100 DayDelta dict."""
    day_wire = {k: v for k, v in result.day.items() if k != "_rich"}
    delta: DayDelta = {
        "seq": int(seq),
        "episode_day": int(episode_day),
        "day": day_wire,
        "live_lots": list(result.live_lots),
        "pipeline": list(result.pipeline),
        "drop_oldest": bool(drop_oldest),
    }
    if result.belief is not None:
        delta["belief"] = dict(result.belief)
    return delta


def current_belief_flat(
    state: DayDriverState,
    *,
    enable_filter: bool,
    L: int,
    K: int,
) -> FlatBelief:
    """Belief for Snapshot / cold start from RBPF or empty prior."""
    from blueberries_voi.simulator.belief import empty_flat_belief

    if enable_filter and state.rbpf is not None and state.rbpf._state is not None:
        return flatten_shelf_belief(shelf_belief_from_rbpf(state.rbpf))
    return empty_flat_belief(L=L, K=K)


def pending_view(pending: MutableMapping[int, int]) -> Mapping[int, int]:
    return dict(pending)


__all__ = [
    "DayAdvanceResult",
    "DayDriverState",
    "advance_day",
    "build_day_delta",
    "current_belief_flat",
    "pending_view",
]

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
from typing import TYPE_CHECKING, Any

import numpy as np

from blueberries_voi.filter.belief import ShelfBelief, shelf_belief_from_rbpf
from blueberries_voi.filter.types import P1Obs
from blueberries_voi.model import Cohort, ModelParams, day_step
from blueberries_voi.model.abdella import shipment_arrival_age
from blueberries_voi.rng import (
    STREAM_ALLOC,
    STREAM_ARRIVAL_SENSOR,
    STREAM_ARRIVAL_SHIP,
    STREAM_DEMAND,
    STREAM_FILTER_RESAMPLE,
    STREAM_SPOIL,
    spawn_rng,
)
from blueberries_voi.simulator.belief import (
    flatten_shelf_belief,
    live_lots_payload,
    pipeline_payload,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping, Sequence

    from blueberries_voi.filter.rbpf import RBPF
    from blueberries_voi.model.abdella import ShipmentTrace
    from blueberries_voi.simulator.belief import DayDelta, FlatBelief


def _case_round_ceil(order_qty: int, case_size: int) -> int:
    """Ceil order quantity to whole cases; zero stays zero (closed-loop convention)."""
    qty = max(0, int(order_qty))
    if qty <= 0:
        return 0
    cases = int(np.ceil(qty / case_size))
    return cases * case_size


def _arrival_age(
    *,
    shipments: Sequence[ShipmentTrace],
    params: ModelParams,
    root_seed: int,
    run_id: str | int,
    day: int,
    spread_scale: float,
) -> float:
    """Bootstrap a shipment age without going through ``sim`` (avoids FS default)."""
    if not shipments:
        msg = "shipments must be non-empty"
        raise ValueError(msg)
    rng_ship = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SHIP)
    rng_sensor = spawn_rng(
        root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SENSOR
    )
    idx = int(rng_ship.integers(0, len(shipments)))
    _ = float(rng_sensor.random())
    ship = shipments[idx]
    age = shipment_arrival_age(ship, q10=params.q10, t_ref_c=params.t_ref_c)
    ages = [
        shipment_arrival_age(s, q10=params.q10, t_ref_c=params.t_ref_c)
        for s in shipments
    ]
    mean_age = float(np.mean(ages))
    return float(mean_age + spread_scale * (age - mean_age))


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
) -> DayAdvanceResult:
    """Run order → pending/arrival → ``day_step`` → obs → optional RBPF → belief.

    Shared by ``EngineSession.step`` / ``act`` so hosts share one physics path.
    """
    if not isinstance(order_qty, (int, np.integer)) or isinstance(order_qty, bool):
        msg = f"order_qty must be an int, got {type(order_qty)!r}"
        raise TypeError(msg)

    day = int(state.episode_day)
    pending: dict[int, int] = dict(state.pending)
    cohorts = list(state.cohorts)
    next_lot_id = int(state.next_lot_id)
    rbpf = state.rbpf

    order_units = _case_round_ceil(int(order_qty), params.case_size)
    pending[day + lead_time] = pending.get(day + lead_time, 0) + order_units

    arrival_units = int(pending.pop(day, 0))
    delivery: Cohort | None = None
    if arrival_units > 0:
        tau_in = _arrival_age(
            shipments=shipments,
            params=params,
            root_seed=root_seed,
            run_id=run_id,
            day=day,
            spread_scale=spread_scale,
        )
        delivery = Cohort(n=arrival_units, tau=tau_in, lot_id=next_lot_id)
        next_lot_id += 1

    rng_d = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_DEMAND)
    rng_a = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_ALLOC)
    rng_s = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_SPOIL)
    result = day_step(
        cohorts,
        params=params,
        delivery=delivery,
        rng_demand=rng_d,
        rng_alloc=rng_a,
        rng_spoil=rng_s,
    )
    cohorts = result.cohorts

    belief_flat: FlatBelief | None = None
    if enable_filter and rbpf is not None:
        obs = P1Obs(
            sales_total=int(result.sales_total),
            waste_total=int(result.waste_total),
            arrivals=int(arrival_units),
        )
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
    delta: DayDelta = {
        "seq": int(seq),
        "episode_day": int(episode_day),
        "day": dict(result.day),
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

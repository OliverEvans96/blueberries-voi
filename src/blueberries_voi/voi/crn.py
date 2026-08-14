"""SIM-02 outer-loop CRN cell: shared physics across knowledge scenarios."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal

from blueberries_voi.controller.damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.controller.ordering import invoke_order
from blueberries_voi.controller.rollout import RolloutPolicy
from blueberries_voi.filter import RBPF
from blueberries_voi.filter.belief import (
    ShelfBelief,
    empty_shelf_belief,
    shelf_belief_from_cohorts_oracle,
    shelf_belief_from_rbpf,
)
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
from blueberries_voi.sim import DayLog, EpisodeLog, generate_arrival_age
from blueberries_voi.sim.alpha_tune import require_tuned_alpha_table
from blueberries_voi.sim.calendar import _EPISODE_CALENDAR_EPOCH
from blueberries_voi.sim.day_tick import (
    enqueue_pending_order,
    lot_states_from_cohorts,
    nonzero_lot_maps,
    pack_date_from_epoch,
    pop_arrival_units,
    pre_live_lot_ids,
)
from blueberries_voi.sim.episode import case_round
from blueberries_voi.sim.profit import DEFAULT_PROFIT_COSTS, ProfitCosts, episode_profit
from blueberries_voi.sim.shipments import default_shipments, smoke_cool_shipments

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date
    from pathlib import Path

    from blueberries_voi.model.abdella import ShipmentTrace

# Shared physics run_id across scenarios (SIM-02=C); filter streams are scenario-keyed.
PHYSICS_RUN_ID: str = "voi-physics"

VOI_SCENARIOS: tuple[str, ...] = (
    "P0",
    "P1",
    "F1",
    "F1s",
    "F2a",
    "F2",
    "B-state",
)

_EMPTY_TAU_GRID: tuple[float, ...] = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0)
_SMOKE_ALPHA: float = 0.9

BeliefKind = Literal["filter", "oracle"]

__all__ = [
    "PHYSICS_RUN_ID",
    "VOI_SCENARIOS",
    "default_shipments",
    "run_voi_crn_cell",
    "smoke_cool_shipments",
]


def _fixture_shipments() -> list[ShipmentTrace]:
    """Deprecated alias for smoke/tests; prefer ``smoke_cool_shipments``."""
    return smoke_cool_shipments()


def _empty_shelf_belief() -> ShelfBelief:
    return empty_shelf_belief(tau_grid=_EMPTY_TAU_GRID)


def _oracle_belief(cohorts: Sequence[Cohort]) -> ShelfBelief:
    return shelf_belief_from_cohorts_oracle(cohorts, empty_tau_grid=_EMPTY_TAU_GRID)


def _belief_kind(scenario: str) -> BeliefKind:
    if scenario == "B-state":
        return "oracle"
    return "filter"


def _run_scenario_episode(
    *,
    scenario: str,
    policy: Any,
    shipments: Sequence[ShipmentTrace],
    params: ModelParams,
    root_seed: int,
    n_burn: int,
    n_score: int,
    lead_time: int,
    filter_n: int,
) -> EpisodeLog:
    """One scenario trajectory sharing physics streams under ``PHYSICS_RUN_ID``."""
    ships = list(shipments)
    cohorts: list[Cohort] = []
    next_lot_id = 1
    pending: dict[int, int] = {}
    log = EpisodeLog(n_burn=n_burn, n_score=n_score)
    horizon = n_burn + n_score
    kind = _belief_kind(scenario)
    filter_run = f"voi-filter-{scenario}"

    rbpf: RBPF | None = None
    if kind == "filter":
        rbpf = RBPF(params=params, N=int(filter_n))
        rbpf._root_seed = int(root_seed)
        rbpf._run_id = filter_run
        init_rng = spawn_rng(
            int(root_seed), run_id=filter_run, day=0, stream=STREAM_FILTER_RESAMPLE
        )
        rbpf.initialize(init_rng)

    for day in range(horizon):
        pending_view: Mapping[int, int] = dict(pending)
        if kind == "oracle":
            belief: ShelfBelief = _oracle_belief(cohorts)
        else:
            assert rbpf is not None
            belief = (
                shelf_belief_from_rbpf(rbpf)
                if rbpf._state is not None
                else _empty_shelf_belief()
            )

        raw_qty = invoke_order(policy, day, belief, pending_view)

        order_units = case_round(raw_qty, params.case_size)
        # No OrderSchedule gate here (behavior freeze vs episode/day_driver).
        enqueue_pending_order(pending, day, lead_time, order_units)

        arrival_units = pop_arrival_units(pending, day)
        delivery: Cohort | None = None
        age_at_receipt: float | None = None
        pack_date: date | None = None
        if arrival_units > 0:
            rng_ship = spawn_rng(
                root_seed, run_id=PHYSICS_RUN_ID, day=day, stream=STREAM_ARRIVAL_SHIP
            )
            rng_sensor = spawn_rng(
                root_seed,
                run_id=PHYSICS_RUN_ID,
                day=day,
                stream=STREAM_ARRIVAL_SENSOR,
            )
            tau_in = generate_arrival_age(rng_ship, rng_sensor, ships, params)
            delivery = Cohort(n=arrival_units, tau=tau_in, lot_id=next_lot_id)
            next_lot_id += 1
            age_at_receipt = float(tau_in)
            pack_date = pack_date_from_epoch(
                day, age_at_receipt, epoch=_EPISODE_CALENDAR_EPOCH
            )

        pre_live_ids = pre_live_lot_ids(cohorts)
        rng_d = spawn_rng(
            root_seed, run_id=PHYSICS_RUN_ID, day=day, stream=STREAM_DEMAND
        )
        rng_a = spawn_rng(
            root_seed, run_id=PHYSICS_RUN_ID, day=day, stream=STREAM_ALLOC
        )
        rng_s = spawn_rng(
            root_seed, run_id=PHYSICS_RUN_ID, day=day, stream=STREAM_SPOIL
        )
        # Keep day= (voi path); m2 intentionally omits it — do not unify.
        result = day_step(
            cohorts,
            params=params,
            delivery=delivery,
            rng_demand=rng_d,
            rng_alloc=rng_a,
            rng_spoil=rng_s,
            day=day,
        )
        cohorts = result.cohorts
        sales_by_lot, waste_by_lot = nonzero_lot_maps(
            pre_live_ids, result.sales_by_cohort, result.waste_by_cohort
        )
        day_log = DayLog(
            day=day,
            lots=lot_states_from_cohorts(cohorts),
            sales_total=result.sales_total,
            waste_total=result.waste_total,
            arrivals=arrival_units,
            order_qty=order_units,
            demand=result.demand,
            L=len(cohorts),
            sales_by_lot=sales_by_lot,
            waste_by_lot=waste_by_lot,
            age_at_receipt=age_at_receipt,
            pack_date=pack_date,
        )
        log.days.append(day_log)

        if kind == "filter" and rbpf is not None:
            mask = mask_for(scenario)
            obs = rich_obs_from_day_log(day_log, mask)
            step_rng = spawn_rng(
                int(root_seed),
                run_id=filter_run,
                day=day,
                stream=STREAM_FILTER_RESAMPLE,
            )
            rbpf.step(obs, step_rng)

    return log


def run_voi_crn_cell(
    *,
    beta: float,
    root_seed: int,
    scenarios: Sequence[str] | None = None,
    n_burn: int = 1,
    n_score: int = 2,
    costs: ProfitCosts | None = None,
    shipments: Sequence[ShipmentTrace] | None = None,
    params: ModelParams | None = None,
    lead_time: int = 1,
    filter_n: int = 32,
    alpha: float = _SMOKE_ALPHA,
    alpha_table_path: str | Path | None = None,
    H: int = 2,
    n_rollout_paths: int = 1,
    policy: Any | None = None,
) -> dict[str, float]:
    """Per-scenario scored episode profit under shared physics CRN (SIM-02=C).

    Physics streams use ``PHYSICS_RUN_ID``. Filter resample streams are keyed by
    scenario. Scorable profit uses ``EpisodeLog.scored`` (after burn-in).

    Production callers pass ``alpha_table_path`` (CTL-03); smoke may omit it and
    keep fixed ``alpha`` (default 0.9). ``shipments=None`` loads Abdella.
    """
    from blueberries_voi.backend import rust_available, warn_fallback_once

    # Rust has no Abdella parquet loader. `shipments=None` stays on Python.
    if rust_available() and shipments is not None:
        warn_fallback_once()
        from blueberries_voi.backend import rust_core

        assert rust_core is not None
        ships = list(shipments)
        times = [list(map(float, getattr(s, "times_d", []))) for s in ships]
        temps = [list(map(float, getattr(s, "temps_c", []))) for s in ships]
        rows = rust_core.run_voi_crn_cell_py(
            float(beta),
            int(root_seed),
            int(n_burn),
            int(n_score),
            int(filter_n),
            int(H),
            int(n_rollout_paths),
            int(lead_time),
            times,
            temps,
        )
        names = list(scenarios) if scenarios is not None else list(VOI_SCENARIOS)
        table = {str(k): float(v) for k, v in rows}
        return {n: table[n] for n in names if n in table}

    names = list(scenarios) if scenarios is not None else list(VOI_SCENARIOS)
    for name in names:
        if name not in VOI_SCENARIOS:
            msg = f"unknown VOI scenario {name!r}; expected one of {VOI_SCENARIOS}"
            raise ValueError(msg)

    base = params or ModelParams()
    p = replace(base, beta=float(beta))
    cost = costs if costs is not None else DEFAULT_PROFIT_COSTS
    ships = list(shipments) if shipments is not None else default_shipments()

    if alpha_table_path is not None:
        alphas = require_tuned_alpha_table(alpha_table_path)
        if "sw" not in alphas:
            msg = (
                "tuned alpha table incomplete for VOI: missing arm 'sw' "
                f"(path={alpha_table_path!s})"
            )
            raise ValueError(msg)
        policy_alpha = float(alphas["sw"])
    else:
        policy_alpha = float(alpha)

    if policy is None:
        sw = DampedSurvivalWeightedPolicy(
            alpha=float(policy_alpha),
            params=p,
        )
        pol: Any = RolloutPolicy(
            base_policy=sw,
            params=p,
            root_seed=int(root_seed),
            run_id="voi-rollout",
            H=int(H),
            n_rollout_paths=int(n_rollout_paths),
            lead_time=int(lead_time),
        )
    else:
        pol = policy

    out: dict[str, float] = {}
    for name in names:
        ep = _run_scenario_episode(
            scenario=name,
            policy=pol,
            shipments=ships,
            params=p,
            root_seed=int(root_seed),
            n_burn=int(n_burn),
            n_score=int(n_score),
            lead_time=int(lead_time),
            filter_n=int(filter_n),
        )
        out[name] = float(episode_profit(ep, cost))
    return out

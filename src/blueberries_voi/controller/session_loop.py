"""EngineSession step loop for custom Python controllers (Option A / ADR 0148).

Closed-loop pattern: ``snapshot`` → ``controller.order(ctx)`` → ``step(order_qty)``
→ optional ``observe``. Does not use ``sim.episode.run_closed_loop_episode``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy  # noqa: TC001
from blueberries_voi.filter.belief import (
    ShelfBelief,
    posterior_unit_mass,
    unflatten_shelf_belief,
)
from blueberries_voi.filter.types import (
    preset_for_channels,
    validate_channels,
)
from blueberries_voi.sim.bakeoff_damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule
from blueberries_voi.sim.profit import (
    DEFAULT_PROFIT_COSTS,
    DEFAULT_STORE_ECONOMICS,
    ProfitCosts,
    StoreEconomics,
    day_profit,
    day_profit_store,
    profit_costs_from_store_economics,
)
from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.sim.types_log import DayLog
from blueberries_voi.simulator import DEMO_BUDGETS, EngineSession


def default_session_config(**overrides: Any) -> dict[str, Any]:
    """Build an ``EngineSession.init`` config dict with smoke-cool defaults."""
    overrides = dict(overrides)
    obs_channels = overrides.pop("obs_channels", None)
    cfg: dict[str, Any] = {
        "shipments": smoke_cool_shipments(),
        "lead_time": int(DEFAULT_ORDER_SCHEDULE.lead_time_days),
        "delivery_weekdays": sorted(
            int(d) for d in DEFAULT_ORDER_SCHEDULE.delivery_weekdays
        ),
        "enable_filter": True,
        "belief_source": "filter",
        "obs_scenario": "P1",
        "n_particles": int(DEMO_BUDGETS["n_particles"]),
        "H": int(DEMO_BUDGETS["H"]),
        "n_rollout_paths": 0,
        "candidate_case_radius": int(DEMO_BUDGETS["candidate_case_radius"]),
        "L": 10,
        "K": 4,
    }
    if obs_channels is not None:
        ch = validate_channels(obs_channels)
        cfg["obs_channels"] = {
            "code_type": ch.code_type,
            "scan_waste": ch.scan_waste,
            "delivery_history": ch.delivery_history,
        }
        preset = preset_for_channels(ch)
        if preset is not None:
            cfg["obs_scenario"] = preset
    cfg.update(overrides)
    return cfg


@dataclass(frozen=True)
class DemandForecast:
    """Committed demand profile from the session snapshot."""

    scale_mu: float
    dow_means: tuple[float, ...]


@dataclass(frozen=True)
class FreshnessBelief:
    """Filter posterior: per-lot freshness marginals on a shared grid."""

    freshness_grid: tuple[float, ...]
    lot_marginals: tuple[tuple[float, ...], ...]

    def expected_freshness(self, lot_index: int) -> float:
        """``E[f]`` for one lot row: ``Σ_k p_{l,k} · freshness_grid[k]``."""
        row = self.lot_marginals[lot_index]
        return float(
            sum(p * f for p, f in zip(row, self.freshness_grid, strict=False))
        )


@dataclass(frozen=True)
class ControllerContext:
    """Pre-step decision view for custom controllers (filter posterior, not truth).

    ``posterior_units`` is optional summed belief mass (not simulator inventory).
    ``inbound_pipeline`` is orders already placed (arrival day → units).
    ``store_economics`` are session business constants (Studio money knobs).
    """

    episode_day: int
    step_seq: int
    belief: FreshnessBelief
    posterior_units: float
    inbound_pipeline: dict[int, int]
    order_schedule: OrderSchedule
    can_order_today: bool
    demand_forecast: DemandForecast
    store_economics: StoreEconomics


def freshness_belief_from_wire(wire: Mapping[str, Any]) -> FreshnessBelief:
    """Build controller-safe belief from snapshot ``belief`` wire (no lot counts)."""
    grid = tuple(float(f) for f in wire["f_grid"])
    k = len(grid)
    flat = [float(x) for x in wire["f_marginals"]]
    l_dim = int(wire.get("L", len(flat) // k if k else 0))
    rows = tuple(tuple(flat[ell * k : (ell + 1) * k]) for ell in range(l_dim))
    return FreshnessBelief(freshness_grid=grid, lot_marginals=rows)


def _slot_masses_from_wire(wire: Mapping[str, Any]) -> list[float]:
    """Per-lot posterior slot masses used only when building ``posterior_units``."""
    raw = wire.get("lot_counts", [])
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [float(x) for x in raw]


def pipeline_wire_to_pending(pipeline: Sequence[Mapping[str, Any]]) -> dict[int, int]:
    """Convert snapshot ``pipeline`` wire rows to ``{arrival_day: qty}``."""
    out: dict[int, int] = {}
    for row in pipeline:
        day = int(row["arrival_day"])
        qty = int(row["qty"])
        if qty != 0:
            out[day] = qty
    return out


def _schedule_from_wire(wire: Mapping[str, Any]) -> OrderSchedule:
    delivery = wire.get("delivery_weekdays")
    if delivery is None:
        return DEFAULT_ORDER_SCHEDULE
    lead = int(wire.get("lead_time_days", DEFAULT_ORDER_SCHEDULE.lead_time_days))
    return OrderSchedule.with_delivery(delivery, lead_time_days=lead)


def _demand_from_snapshot(snap: Mapping[str, Any]) -> DemandForecast:
    wire = snap.get("demand_summary")
    if isinstance(wire, Mapping):
        scale = float(wire.get("scale_mu", 0.0))
        raw_means = wire.get("dow_means", [])
        if isinstance(raw_means, Sequence) and not isinstance(raw_means, (str, bytes)):
            means = tuple(float(x) for x in raw_means)
            return DemandForecast(scale_mu=scale, dow_means=means)
    return DemandForecast(scale_mu=0.0, dow_means=())


def context_from_snapshot(
    snap: Mapping[str, Any],
    *,
    store_economics: StoreEconomics = DEFAULT_STORE_ECONOMICS,
) -> ControllerContext:
    """Build a ``ControllerContext`` from an ``EngineSession`` snapshot mapping."""
    belief_wire = snap["belief"]
    belief = freshness_belief_from_wire(belief_wire)
    slot_masses = _slot_masses_from_wire(belief_wire)
    posterior_units = posterior_unit_mass(
        belief.lot_marginals,
        slot_masses=slot_masses,
    )
    schedule_wire = snap.get("schedule")
    order_schedule = (
        _schedule_from_wire(schedule_wire)
        if isinstance(schedule_wire, Mapping)
        else DEFAULT_ORDER_SCHEDULE
    )
    episode_day = int(snap.get("episode_day", 0))
    pipeline_raw = snap.get("pipeline", [])
    is_seq = isinstance(pipeline_raw, Sequence) and not isinstance(
        pipeline_raw, (str, bytes)
    )
    inbound = pipeline_wire_to_pending(pipeline_raw) if is_seq else {}
    return ControllerContext(
        episode_day=episode_day,
        step_seq=int(snap.get("seq", 0)),
        belief=belief,
        posterior_units=posterior_units,
        inbound_pipeline=inbound,
        order_schedule=order_schedule,
        can_order_today=order_schedule.can_order(episode_day),
        demand_forecast=_demand_from_snapshot(snap),
        store_economics=store_economics,
    )


@dataclass(frozen=True)
class ControllerStepLog:
    """One scored day from the Option A step loop."""

    episode_day: int
    seq: int
    order_qty: int
    sales_total: int
    waste_total: int
    demand: int
    arrivals: int
    on_hand: int
    day_profit: float

    @classmethod
    def from_delta(
        cls,
        delta: Mapping[str, Any],
        *,
        costs: ProfitCosts | None = None,
        store_economics: StoreEconomics | None = None,
    ) -> ControllerStepLog:
        day = delta["day"]
        if not isinstance(day, Mapping):
            msg = "DayDelta.day must be a mapping"
            raise TypeError(msg)
        day_log = DayLog(
            day=int(day.get("day", delta.get("episode_day", 0))),
            lots=[],
            sales_total=int(day.get("sales_total", 0)),
            waste_total=int(day.get("waste_total", 0)),
            arrivals=int(day.get("arrivals", 0)),
            order_qty=int(day.get("order_qty", 0)),
            demand=int(day.get("demand", 0)),
            L=int(day.get("L", 0)),
        )
        if store_economics is not None:
            profit = float(day_profit_store(day_log, store_economics))
        else:
            profit = float(day_profit(day_log, costs or DEFAULT_PROFIT_COSTS))
        return ControllerStepLog(
            episode_day=int(delta.get("episode_day", day_log.day)),
            seq=int(delta.get("seq", 0)),
            order_qty=day_log.order_qty,
            sales_total=day_log.sales_total,
            waste_total=day_log.waste_total,
            demand=day_log.demand,
            arrivals=day_log.arrivals,
            on_hand=day_log.L,
            day_profit=profit,
        )


@runtime_checkable
class ControllerProtocol(Protocol):
    """Minimal controller surface for ``run_controller_session``."""

    def order(self, ctx: ControllerContext) -> int: ...


@runtime_checkable
class LearningController(ControllerProtocol, Protocol):
    """Controller that updates from ``observe`` after each step."""

    def observe(self, ctx: ControllerContext, log: ControllerStepLog) -> None: ...


class PolicyController:
    """Adapter for library policies with day-first or belief-first ``order``."""

    def __init__(
        self,
        policy: CorrectedAgeBlindPolicy | DampedSurvivalWeightedPolicy,
    ) -> None:
        self._policy = policy

    def order(
        self,
        ctx: ControllerContext,
        shelf: ShelfBelief,
    ) -> int:
        if not ctx.can_order_today:
            return 0
        pending = ctx.inbound_pipeline
        schedule = ctx.order_schedule
        if isinstance(self._policy, DampedSurvivalWeightedPolicy):
            return int(
                self._policy.order(
                    shelf,
                    day=ctx.episode_day,
                    pending_orders=pending,
                    schedule=schedule,
                )
            )
        return int(
            self._policy.order(
                ctx.episode_day,
                shelf,
                pending_orders=pending,
                schedule=schedule,
            )
        )


@dataclass(frozen=True)
class EpisodeTotals:
    """Episode-level aggregates for benchmark charts."""

    profit: float
    waste: int
    stockout: int
    seed: int
    policy_label: str


def episode_totals_from_logs(
    logs: Sequence[ControllerStepLog],
    costs: ProfitCosts = DEFAULT_PROFIT_COSTS,
    *,
    seed: int = 0,
    policy_label: str = "",
) -> EpisodeTotals:
    """Sum profit, waste, and lost-sales stockout from controller step logs."""
    _ = costs  # day_profit already applied on each log
    profit = sum(log.day_profit for log in logs)
    waste = sum(log.waste_total for log in logs)
    stockout = sum(max(0, log.demand - log.sales_total) for log in logs)
    return EpisodeTotals(
        profit=profit,
        waste=waste,
        stockout=stockout,
        seed=seed,
        policy_label=policy_label,
    )


def run_controller_episode(
    session_cfg: Mapping[str, Any],
    controller: ControllerProtocol,
    seed: int,
    n_days: int,
    *,
    store_economics: StoreEconomics = DEFAULT_STORE_ECONOMICS,
    policy_label: str = "",
) -> EpisodeTotals:
    """Run ``n_days`` of Option A controller loop and return episode aggregates."""
    if n_days < 0:
        msg = f"n_days must be non-negative, got {n_days}"
        raise ValueError(msg)
    session = EngineSession()
    session.init(session_cfg, seed=seed)
    logs = run_controller_session(
        session, controller, n_days, store_economics=store_economics
    )
    costs = profit_costs_from_store_economics(store_economics)
    return episode_totals_from_logs(
        logs,
        costs,
        seed=seed,
        policy_label=policy_label,
    )


def run_act_episode(
    session_cfg: Mapping[str, Any],
    seed: int,
    n_days: int,
    policy: str,
    *,
    store_economics: StoreEconomics = DEFAULT_STORE_ECONOMICS,
    policy_label: str | None = None,
    **act_kw: Any,
) -> EpisodeTotals:
    """Run ``n_days`` of ``EngineSession.act`` and return episode aggregates."""
    if n_days < 0:
        msg = f"n_days must be non-negative, got {n_days}"
        raise ValueError(msg)
    session = EngineSession()
    session.init(session_cfg, seed=seed)
    logs: list[ControllerStepLog] = []
    for _ in range(n_days):
        delta = session.act(policy=policy, **act_kw)
        logs.append(
            ControllerStepLog.from_delta(delta, store_economics=store_economics)
        )
    label = policy if policy_label is None else policy_label
    costs = profit_costs_from_store_economics(store_economics)
    return episode_totals_from_logs(
        logs,
        costs,
        seed=seed,
        policy_label=label,
    )


def run_controller_session(
    session: EngineSession,
    controller: ControllerProtocol,
    n_days: int,
    *,
    store_economics: StoreEconomics = DEFAULT_STORE_ECONOMICS,
) -> list[ControllerStepLog]:
    """Run ``n_days`` of snapshot → order → step with optional ``observe`` hook."""
    if n_days < 0:
        msg = f"n_days must be non-negative, got {n_days}"
        raise ValueError(msg)
    logs: list[ControllerStepLog] = []
    for _ in range(n_days):
        snap = session.snapshot()
        ctx = context_from_snapshot(snap, store_economics=store_economics)
        shelf = unflatten_shelf_belief(snap["belief"])
        ctrl_any: Any = controller
        if isinstance(ctrl_any, PolicyController):
            order_qty = int(ctrl_any.order(ctx, shelf))
        else:
            order_qty = int(controller.order(ctx))
        delta = session.step(order_qty)
        log = ControllerStepLog.from_delta(delta, store_economics=store_economics)
        if isinstance(controller, LearningController):
            controller.observe(ctx, log)
        logs.append(log)
    return logs


__all__ = [
    "ControllerContext",
    "ControllerProtocol",
    "ControllerStepLog",
    "DemandForecast",
    "EpisodeTotals",
    "FreshnessBelief",
    "LearningController",
    "PolicyController",
    "context_from_snapshot",
    "default_session_config",
    "episode_totals_from_logs",
    "freshness_belief_from_wire",
    "pipeline_wire_to_pending",
    "run_act_episode",
    "run_controller_episode",
    "run_controller_session",
]

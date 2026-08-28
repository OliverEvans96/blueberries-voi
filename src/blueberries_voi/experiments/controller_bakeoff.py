"""Rust controller bakeoff shards (notebook 21).

Compares ladder controllers under oracle shelf (SIM-01=B) or optional filtered
beliefs via ``EngineSession.act``. Excludes rollout and dp per T-163 bakeoff plan.
"""

from __future__ import annotations

import itertools
import json
import os
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

from blueberries_voi.experiments.rollout_bakeoff import DEFAULT_ROLLOUT_SEEDS
from blueberries_voi.experiments.voi_profit import (
    DEFAULT_FILTER_N,
    profit_session_config,
)
from blueberries_voi.filter.types import (
    ObsChannels,
    channels_for_preset,
    validate_channels,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.sim.alpha_tune import (
    evaluate_alpha_episode_outcomes,
    require_tuned_alpha_table,
)
from blueberries_voi.sim.bakeoff_damped_sw import protection_demand_quantile
from blueberries_voi.sim.bakeoff_ordering import ConstantOrderPolicy
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE
from blueberries_voi.sim.profit import DEFAULT_PROFIT_COSTS, ProfitCosts, day_profit
from blueberries_voi.sim.service import service_metrics_from_steps
from blueberries_voi.sim.shipments import default_shipments
from blueberries_voi.sim.types_log import DayLog
from blueberries_voi.simulator import EngineSession

BeliefWorld = Literal["oracle", "filtered"]

BAKEOFF_ARMS: tuple[str, ...] = ("constant", "rung0", "sw", "sla_pb")
FILTERED_ARMS: tuple[str, ...] = ("constant", "sw", "sla_pb")
FILTERED_OBS_PRESET: str = "F3"
DEFAULT_CONTROLLER_SEEDS: tuple[int, ...] = DEFAULT_ROLLOUT_SEEDS[:10]
DEFAULT_N_BURN = 2
DEFAULT_N_SCORE = 14
PRODUCTION_N_SCORE = 45
DEFAULT_RHO = 0.8
DEFAULT_N_SLA_PATHS = 16
DEFAULT_TUNED_ALPHA_PATH = "experiments/tuned_alpha.json"
DEFAULT_SLA_PB_BO_PATH = "experiments/sla_pb_alpha_bo.json"

ARM_LABELS: dict[str, str] = {
    "constant": "Fixed order",
    "rung0": "Rung 0 (age-blind)",
    "sw": "Damped SW",
    "sla_pb": "Window SLA (PB)",
}

__all__ = [
    "ARM_LABELS",
    "BAKEOFF_ARMS",
    "DEFAULT_CONTROLLER_SEEDS",
    "DEFAULT_FILTER_N",
    "DEFAULT_N_BURN",
    "DEFAULT_N_SCORE",
    "DEFAULT_N_SLA_PATHS",
    "DEFAULT_RHO",
    "DEFAULT_SLA_PB_BO_PATH",
    "DEFAULT_TUNED_ALPHA_PATH",
    "FILTERED_ARMS",
    "FILTERED_OBS_PRESET",
    "PRODUCTION_N_SCORE",
    "BeliefWorld",
    "arms_for_belief_world",
    "belief_world_from_env",
    "controller_bakeoff_job_grid",
    "filtered_obs_channels",
    "merge_controller_bakeoff_rows",
    "resolve_arm_alpha",
    "resolve_arm_rho",
    "run_controller_eval",
]


def belief_world_from_env() -> BeliefWorld:
    """Read ``BELIEF_WORLD`` (``oracle`` default, or ``filtered``)."""
    raw = os.environ.get("BELIEF_WORLD", "oracle").strip().lower()
    if raw == "filtered":
        return "filtered"
    return "oracle"


def filtered_obs_channels(
    channels: ObsChannels | dict[str, object] | None = None,
) -> ObsChannels:
    """Default P1 obs for filtered belief bakeoff unless overridden."""
    if channels is not None:
        return validate_channels(channels)
    return channels_for_preset(FILTERED_OBS_PRESET)


def arms_for_belief_world(belief_world: BeliefWorld | str) -> tuple[str, ...]:
    """Oracle grid is four arms; filtered omits rung0 (no ``session.act`` support)."""
    if str(belief_world).lower() == "filtered":
        return FILTERED_ARMS
    return BAKEOFF_ARMS


def _load_tuned_alpha_header(
    alpha_table_path: Path | str | None = None,
) -> dict[str, Any]:
    path = Path(alpha_table_path or DEFAULT_TUNED_ALPHA_PATH)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    header = data.get("header")
    return dict(header) if isinstance(header, dict) else {}


def resolve_arm_alpha(
    arm_id: str,
    *,
    alpha: float | None = None,
    alpha_table_path: Path | str | None = None,
) -> float:
    """Per-arm tuned alpha when not overridden."""
    if alpha is not None:
        return float(alpha)
    path = alpha_table_path or DEFAULT_TUNED_ALPHA_PATH
    try:
        table = require_tuned_alpha_table(path)
    except (ValueError, OSError):
        return 0.9
    if arm_id in table:
        return float(table[arm_id])
    return 0.9


def resolve_arm_rho(
    arm_id: str,
    *,
    rho: float | None = None,
    default_rho: float = DEFAULT_RHO,
    alpha_table_path: Path | str | None = None,
    sla_pb_bo_path: Path | str | None = None,
) -> float:
    """Per-arm tuned rho when not overridden (``sla_pb`` SOO uses rho~0.5)."""
    if rho is not None:
        return float(rho)
    if arm_id == "sla_pb":
        header = _load_tuned_alpha_header(alpha_table_path)
        if "sla_pb_bo_rho" in header:
            return float(header["sla_pb_bo_rho"])
        bo_path = Path(sla_pb_bo_path or DEFAULT_SLA_PB_BO_PATH)
        if bo_path.is_file():
            payload = json.loads(bo_path.read_text(encoding="utf-8"))
            key = "best_rho_profit_soo"
            if key not in payload:
                key = "best_rho_profit_moo"
            if key in payload:
                return float(payload[key])
    if arm_id == "sw":
        from blueberries_voi.experiments.voi_profit import load_damped_sw_bo_params

        _, sw_rho = load_damped_sw_bo_params()
        return float(sw_rho)
    return float(default_rho)


def _constant_order_qty(alpha: float, params: ModelParams | None = None) -> int:
    p = params or ModelParams()
    seed_day = next(
        (d for d in range(7) if DEFAULT_ORDER_SCHEDULE.can_order(d)),
        0,
    )
    prot = int(DEFAULT_ORDER_SCHEDULE.protection_days(seed_day))
    d_star = protection_demand_quantile(
        alpha, p, protection_days=prot, start_day=seed_day
    )
    return int(
        ConstantOrderPolicy(round(d_star), case_size=int(p.case_size)).order(
            None, day=seed_day, pending_orders=()
        )
    )


def _act_kw(
    arm_id: str,
    alpha: float,
    rho: float,
    *,
    n_sla_paths: int,
) -> dict[str, Any]:
    if arm_id == "constant":
        return {"policy": "constant", "order_qty": _constant_order_qty(alpha)}
    if arm_id == "sw":
        return {"policy": "sw", "alpha": float(alpha), "rho": float(rho)}
    if arm_id == "sla_pb":
        return {"policy": "sla_pb", "alpha": float(alpha), "rho": float(rho)}
    msg = f"arm {arm_id!r} has no session.act mapping; use oracle path for rung0"
    raise ValueError(msg)


def _day_log_from_delta(day_idx: int, delta: dict[str, Any]) -> DayLog:
    day = delta["day"]
    return DayLog(
        day=day_idx,
        lots=[],
        sales_total=int(day["sales_total"]),
        waste_total=int(day["waste_total"]),
        arrivals=int(day.get("arrivals", 0)),
        order_qty=int(day["order_qty"]),
        demand=int(day["demand"]),
        L=0,
    )


def _shard_n_score(arm_id: str, n_score: int, budgets: dict[str, Any]) -> int:
    """Allow per-arm scored-day overrides."""
    key = f"{arm_id}_n_score"
    if key in budgets:
        return int(budgets[key])
    return int(n_score)


def _shard_n_sla_paths(arm_id: str, n_sla_paths: int, budgets: dict[str, Any]) -> int:
    return int(n_sla_paths)


def _run_oracle_episode(
    arm_id: str,
    alpha: float,
    seed: int,
    rho: float,
    *,
    n_burn: int,
    n_score: int,
) -> tuple[float, int, int, float, float]:
    outcomes = evaluate_alpha_episode_outcomes(
        arm_id,
        float(alpha),
        int(seed),
        rho=float(rho),
        shipments=default_shipments(),
        n_burn=n_burn,
        n_score=n_score,
    )
    return (
        float(outcomes.profit),
        int(outcomes.total_waste),
        int(outcomes.total_lost_sales),
        float(outcomes.fill_rate),
        float(outcomes.day_no_stockout_rate),
    )


def _run_filtered_episode(
    arm_id: str,
    alpha: float,
    seed: int,
    rho: float,
    *,
    n_burn: int,
    n_score: int,
    n_sla_paths: int,
    filter_n: int,
    channels: ObsChannels,
    costs: ProfitCosts,
) -> tuple[float, int, int, float, float]:
    session = EngineSession()
    session.init(profit_session_config(filter_n=filter_n), seed=int(seed))
    session.set_obs_channels(channels)
    act_kw = _act_kw(arm_id, alpha, rho, n_sla_paths=n_sla_paths)
    for _ in range(n_burn):
        session.act(**act_kw)
    profit = 0.0
    waste = 0
    stockout = 0
    scored_steps: list[DayLog] = []
    for day_idx in range(n_score):
        delta = session.act(**act_kw)
        log = _day_log_from_delta(n_burn + day_idx, delta)
        scored_steps.append(log)
        profit += day_profit(log, costs)
        waste += log.waste_total
        stockout += max(0, log.demand - log.sales_total)
    service = service_metrics_from_steps(scored_steps)
    return (
        profit,
        waste,
        stockout,
        float(service.fill_rate),
        float(service.day_no_stockout_rate),
    )


def run_controller_eval(
    seed: int,
    arm_id: str,
    rho: float,
    *,
    alpha: float | None = None,
    belief_world: BeliefWorld | str = "oracle",
    n_burn: int = DEFAULT_N_BURN,
    n_score: int = DEFAULT_N_SCORE,
    n_sla_paths: int = DEFAULT_N_SLA_PATHS,
    filter_n: int = DEFAULT_FILTER_N,
    channels: ObsChannels | dict[str, object] | None = None,
    costs: ProfitCosts | None = None,
    alpha_table_path: Path | str | None = None,
    **budgets: Any,
) -> dict[str, Any]:
    """Score one ``(seed, arm)`` cell; records wall time as ``elapsed_s``."""
    world = str(belief_world).lower()
    if world == "filtered" and arm_id == "rung0":
        msg = "rung0 is oracle-only; excluded from filtered belief_world grid"
        raise ValueError(msg)
    arm_alpha = resolve_arm_alpha(
        arm_id, alpha=alpha, alpha_table_path=alpha_table_path
    )
    arm_rho = resolve_arm_rho(
        arm_id,
        default_rho=DEFAULT_RHO,
        alpha_table_path=alpha_table_path,
    )
    score_days = _shard_n_score(arm_id, n_score, budgets)
    sla_paths = _shard_n_sla_paths(arm_id, n_sla_paths, budgets)
    use_costs = costs if costs is not None else DEFAULT_PROFIT_COSTS
    t0 = perf_counter()
    if world == "filtered":
        ch = filtered_obs_channels(channels)
        (
            profit,
            waste,
            stockout,
            fill_rate,
            day_no_stockout_rate,
        ) = _run_filtered_episode(
            arm_id,
            arm_alpha,
            int(seed),
            arm_rho,
            n_burn=n_burn,
            n_score=score_days,
            n_sla_paths=sla_paths,
            filter_n=filter_n,
            channels=ch,
            costs=use_costs,
        )
    else:
        profit, waste, stockout, fill_rate, day_no_stockout_rate = _run_oracle_episode(
            arm_id,
            arm_alpha,
            int(seed),
            arm_rho,
            n_burn=n_burn,
            n_score=score_days,
        )
    elapsed = perf_counter() - t0
    return {
        "seed": int(seed),
        "arm_id": str(arm_id),
        "alpha": float(arm_alpha),
        "rho": float(arm_rho),
        "belief_world": world,
        "profit": float(profit),
        "waste": int(waste),
        "stockout": int(stockout),
        "fill_rate": float(fill_rate),
        "day_no_stockout_rate": float(day_no_stockout_rate),
        "n_burn": int(n_burn),
        "n_score": int(score_days),
        "n_sla_paths": 0,
        "elapsed_s": float(elapsed),
    }


def controller_bakeoff_job_grid(
    seeds: Sequence[int],
    arms: Sequence[str],
    rho: float = DEFAULT_RHO,
    *,
    alpha_table_path: Path | str | None = None,
    sla_pb_bo_path: Path | str | None = None,
) -> list[tuple[int, str, float]]:
    """Cartesian product of seeds and arms with per-arm tuned rho."""
    return [
        (
            int(seed),
            str(arm),
            resolve_arm_rho(
                arm,
                default_rho=float(rho),
                alpha_table_path=alpha_table_path,
                sla_pb_bo_path=sla_pb_bo_path,
            ),
        )
        for seed, arm in itertools.product(seeds, arms)
    ]


def merge_controller_bakeoff_rows(
    shards: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Dedup on ``(seed, arm_id, belief_world)``."""
    seen: set[tuple[int, str, str]] = set()
    out: list[dict[str, Any]] = []
    for shard in shards:
        world = str(shard.get("belief_world", "oracle"))
        key = (int(shard["seed"]), str(shard["arm_id"]), world)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(shard))
    return sorted(
        out,
        key=lambda r: (r.get("belief_world", "oracle"), r["arm_id"], int(r["seed"])),
    )

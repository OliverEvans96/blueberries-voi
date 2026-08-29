"""Closed-loop profit shards keyed by ``ObsChannels`` (notebook 15)."""

from __future__ import annotations

import itertools
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from blueberries_voi.experiments.filter_accuracy import PRESET_BY_KEY
from blueberries_voi.filter.types import (
    ObsChannels,
    channels_cache_key,
    validate_channels,
)
from blueberries_voi.sim.alpha_tune import require_tuned_alpha_table
from blueberries_voi.sim.profit import DEFAULT_PROFIT_COSTS, ProfitCosts, day_profit
from blueberries_voi.sim.shipments import default_shipments
from blueberries_voi.sim.types_log import DayLog
from blueberries_voi.simulator import DEMO_BUDGETS, EngineSession

DEFAULT_PROFIT_SEEDS: tuple[int, ...] = (42, 7, 101, 2024)
DEFAULT_N_BURN = 2
DEFAULT_N_SCORE = 30
DEFAULT_FILTER_N = 24
DEFAULT_TUNED_ALPHA_PATH = Path("experiments/tuned_alpha.json")
DEFAULT_CONTROLLER_RHO: float = 0.8
DEFAULT_DAMPED_SW_BO_PATH = Path("outputs/damped_sw_alpha_bo.json")

__all__ = [
    "DEFAULT_CONTROLLER_RHO",
    "DEFAULT_DAMPED_SW_BO_PATH",
    "DEFAULT_FILTER_N",
    "DEFAULT_N_BURN",
    "DEFAULT_N_SCORE",
    "DEFAULT_PROFIT_SEEDS",
    "DEFAULT_TUNED_ALPHA_PATH",
    "load_damped_sw_bo_params",
    "merge_voi_profit_rows",
    "order_divergence_vs_reference",
    "run_seed_channel_profit",
    "run_seed_oracle_profit",
    "voi_profit_job_grid",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _tuned_alpha_path(alpha_table_path: Path | str | None = None) -> Path:
    if alpha_table_path is not None:
        return Path(alpha_table_path)
    env = os.environ.get("BLUEBERRIES_VOI_TUNED_ALPHA")
    if env:
        return Path(env)
    return _repo_root() / DEFAULT_TUNED_ALPHA_PATH


def _tuned_sw_alpha(
    alpha_table_path: Path | str | None = None,
) -> float:
    path = _tuned_alpha_path(alpha_table_path)
    table = require_tuned_alpha_table(path)
    if "sw" not in table:
        msg = f"tuned alpha table missing 'sw' arm: {path}"
        raise ValueError(msg)
    return float(table["sw"])


def load_damped_sw_bo_params(
    bo_json_path: Path | str | None = None,
    *,
    alpha_table_path: Path | str | None = None,
) -> tuple[float, float]:
    """Return ``(alpha, rho)`` from Ax BO JSON or tuned-alpha fallbacks."""
    if bo_json_path is not None:
        path = Path(bo_json_path)
    else:
        path = _repo_root() / DEFAULT_DAMPED_SW_BO_PATH
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        alpha_key = "best_alpha_profit_soo"
        rho_key = "best_rho_profit_soo"
        if alpha_key not in payload:
            alpha_key = "best_alpha_profit_moo"
            rho_key = "best_rho_profit_moo"
        return float(payload[alpha_key]), float(payload[rho_key])
    return _tuned_sw_alpha(alpha_table_path), DEFAULT_CONTROLLER_RHO


def _resolve_controller_params(
    *,
    controller_alpha: float | None,
    controller_rho: float | None,
    bo_json_path: Path | str | None,
    alpha_table_path: Path | str | None,
) -> tuple[float, float]:
    if controller_alpha is not None and controller_rho is not None:
        return float(controller_alpha), float(controller_rho)
    alpha, rho = load_damped_sw_bo_params(
        bo_json_path,
        alpha_table_path=alpha_table_path,
    )
    if controller_alpha is not None:
        alpha = float(controller_alpha)
    if controller_rho is not None:
        rho = float(controller_rho)
    return alpha, rho


def _policy_act_kw(
    alpha: float,
    rho: float,
    *,
    policy: str = "damped_sw",
    n_rollout_paths: int = 0,
) -> dict[str, Any]:
    return {
        "policy": str(policy),
        "alpha": float(alpha),
        "rho": float(rho),
        "n_rollout_paths": int(n_rollout_paths),
    }


def _damped_sw_act_kw(
    alpha: float,
    rho: float,
    *,
    n_rollout_paths: int = 0,
) -> dict[str, Any]:
    return _policy_act_kw(
        alpha, rho, policy="damped_sw", n_rollout_paths=n_rollout_paths
    )


def profit_session_config(
    *,
    n_rollout_paths: int = 0,
    filter_n: int = DEFAULT_FILTER_N,
    alpha_table_path: Path | str | None = None,
) -> dict[str, Any]:
    """EngineSession config for damped-SW closed-loop profit (nb15)."""
    return {
        "shipments": default_shipments(),
        "n_particles": int(filter_n),
        "H": int(DEMO_BUDGETS["H"]),
        "n_rollout_paths": int(n_rollout_paths),
        "candidate_case_radius": int(DEMO_BUDGETS["candidate_case_radius"]),
        "L": 3,
        "K": 8,
        "enable_filter": True,
        "belief_source": "filter",
        "lead_time": 1,
        "obs_scenario": "P0",
        "alpha": _tuned_sw_alpha(alpha_table_path),
    }


def oracle_session_config(
    *,
    n_rollout_paths: int = 0,
    filter_n: int = DEFAULT_FILTER_N,
    alpha_table_path: Path | str | None = None,
) -> dict[str, Any]:
    """EngineSession config for perfect-belief oracle profit (nb17 ceiling row)."""
    cfg = profit_session_config(
        n_rollout_paths=n_rollout_paths,
        filter_n=filter_n,
        alpha_table_path=alpha_table_path,
    )
    cfg["belief_source"] = "truth"
    cfg["enable_filter"] = False
    return cfg


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


def _run_scored_episode(
    seed: int,
    *,
    n_burn: int,
    n_score: int,
    n_rollout_paths: int,
    filter_n: int,
    alpha: float,
    rho: float,
    setup: Any,
    costs: ProfitCosts,
    session_config: dict[str, Any] | None = None,
    policy: str = "damped_sw",
) -> tuple[float, int, int]:
    session = EngineSession()
    cfg = session_config or profit_session_config(
        n_rollout_paths=n_rollout_paths,
        filter_n=filter_n,
    )
    session.init(cfg, seed=seed)
    setup(session)

    act_kw = _policy_act_kw(
        alpha, rho, policy=policy, n_rollout_paths=n_rollout_paths
    )
    for _ in range(n_burn):
        session.act(**act_kw)

    profit = 0.0
    waste = 0
    stockout = 0
    for day_idx in range(n_score):
        delta = session.act(**act_kw)
        log = _day_log_from_delta(n_burn + day_idx, delta)
        profit += day_profit(log, costs)
        waste += log.waste_total
        stockout += max(0, log.demand - log.sales_total)
    return profit, waste, stockout


def _channel_row(
    seed: int,
    channels: ObsChannels,
    *,
    profit: float,
    waste: int,
    stockout: int,
    oracle: bool = False,
) -> dict[str, Any]:
    key = "B-state" if oracle else channels_cache_key(channels)
    row: dict[str, Any] = {
        "seed": int(seed),
        "key": key,
        "profit": float(profit),
        "waste": int(waste),
        "stockout": int(stockout),
    }
    if oracle:
        row["oracle"] = True
        row["preset"] = "B-state"
    else:
        row["code_type"] = channels.code_type
        row["scan_waste"] = bool(channels.scan_waste)
        row["delivery_history"] = channels.delivery_history
        row["preset"] = PRESET_BY_KEY.get(key, "custom")
    return row


def run_seed_channel_profit(
    seed: int,
    channels: ObsChannels | dict[str, object],
    *,
    n_burn: int = DEFAULT_N_BURN,
    n_score: int = DEFAULT_N_SCORE,
    n_rollout_paths: int = 0,
    filter_n: int = DEFAULT_FILTER_N,
    costs: ProfitCosts | None = None,
    alpha_table_path: Path | str | None = None,
    controller_alpha: float | None = None,
    controller_rho: float | None = None,
    bo_json_path: Path | str | None = None,
    policy: str = "damped_sw",
) -> dict[str, Any]:
    """One closed-loop episode: ``init`` → ``set_obs_channels`` → ``act`` loop."""
    ch = validate_channels(channels)
    use_costs = costs if costs is not None else DEFAULT_PROFIT_COSTS
    alpha, rho = _resolve_controller_params(
        controller_alpha=controller_alpha,
        controller_rho=controller_rho,
        bo_json_path=bo_json_path,
        alpha_table_path=alpha_table_path,
    )

    def _setup(session: EngineSession) -> None:
        session.set_obs_channels(ch)

    profit, waste, stockout = _run_scored_episode(
        seed,
        n_burn=n_burn,
        n_score=n_score,
        n_rollout_paths=n_rollout_paths,
        filter_n=filter_n,
        alpha=alpha,
        rho=rho,
        setup=_setup,
        costs=use_costs,
        policy=policy,
    )
    return _channel_row(
        seed,
        ch,
        profit=profit,
        waste=waste,
        stockout=stockout,
    )


def run_seed_oracle_profit(
    seed: int,
    *,
    n_burn: int = DEFAULT_N_BURN,
    n_score: int = DEFAULT_N_SCORE,
    n_rollout_paths: int = 0,
    filter_n: int = DEFAULT_FILTER_N,
    costs: ProfitCosts | None = None,
    alpha_table_path: Path | str | None = None,
    controller_alpha: float | None = None,
    controller_rho: float | None = None,
    bo_json_path: Path | str | None = None,
    policy: str = "damped_sw",
) -> dict[str, Any]:
    """B-state ceiling via ``EngineSession`` truth belief.

    Uses the same physics and policy stack as channel profit rows.
    """
    use_costs = costs if costs is not None else DEFAULT_PROFIT_COSTS
    alpha, rho = _resolve_controller_params(
        controller_alpha=controller_alpha,
        controller_rho=controller_rho,
        bo_json_path=bo_json_path,
        alpha_table_path=alpha_table_path,
    )
    ch = validate_channels(
        {"code_type": "upc", "scan_waste": False, "delivery_history": "none"}
    )

    profit, waste, stockout = _run_scored_episode(
        seed,
        n_burn=n_burn,
        n_score=n_score,
        n_rollout_paths=n_rollout_paths,
        filter_n=filter_n,
        alpha=alpha,
        rho=rho,
        setup=lambda _session: None,
        costs=use_costs,
        session_config=oracle_session_config(
            n_rollout_paths=n_rollout_paths,
            filter_n=filter_n,
            alpha_table_path=alpha_table_path,
        ),
        policy=policy,
    )
    return _channel_row(
        seed,
        ch,
        profit=profit,
        waste=waste,
        stockout=stockout,
        oracle=True,
    )


def voi_profit_job_grid(
    seeds: tuple[int, ...],
    channels: Sequence[ObsChannels],
) -> list[tuple[int, ObsChannels]]:
    """Cartesian product of seeds and channels."""
    return [
        (int(seed), validate_channels(ch))
        for seed, ch in itertools.product(seeds, channels)
    ]


def merge_voi_profit_rows(shards: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedup on ``(seed, key)``; stable sort for DataFrames."""
    seen: set[tuple[int, str]] = set()
    out: list[dict[str, Any]] = []
    for shard in shards:
        key = (int(shard["seed"]), str(shard["key"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(shard))
    return sorted(out, key=lambda r: (r.get("key", ""), int(r["seed"])))


def _collect_orders(
    seed: int,
    channels: ObsChannels,
    *,
    n_days: int,
    n_rollout_paths: int,
    filter_n: int,
    alpha: float,
    rho: float = DEFAULT_CONTROLLER_RHO,
) -> list[int]:
    session = EngineSession()
    cfg = profit_session_config(
        n_rollout_paths=n_rollout_paths,
        filter_n=filter_n,
    )
    session.init(cfg, seed=seed)
    session.set_obs_channels(channels)
    act_kw = _damped_sw_act_kw(alpha, rho, n_rollout_paths=n_rollout_paths)
    orders: list[int] = []
    for _ in range(n_days):
        delta = session.act(**act_kw)
        orders.append(int(delta["day"]["order_qty"]))
    return orders


def order_divergence_vs_reference(
    seed: int,
    channels: ObsChannels | dict[str, object],
    reference: ObsChannels | dict[str, object],
    *,
    n_days: int = 30,
    n_rollout_paths: int = 0,
    filter_n: int = DEFAULT_FILTER_N,
    alpha_table_path: Path | str | None = None,
) -> dict[str, Any]:
    """Compare closed-loop order paths (cheap in-kernel diagnostic)."""
    ch = validate_channels(channels)
    ref = validate_channels(reference)
    alpha, rho = load_damped_sw_bo_params(
        None,
        alpha_table_path=alpha_table_path,
    )
    ref_orders = _collect_orders(
        seed,
        ref,
        n_days=n_days,
        n_rollout_paths=n_rollout_paths,
        filter_n=filter_n,
        alpha=alpha,
        rho=rho,
    )
    test_orders = _collect_orders(
        seed,
        ch,
        n_days=n_days,
        n_rollout_paths=n_rollout_paths,
        filter_n=filter_n,
        alpha=alpha,
        rho=rho,
    )
    diffs = [abs(a - b) for a, b in zip(test_orders, ref_orders, strict=True)]
    n_diff = sum(1 for a, b in zip(test_orders, ref_orders, strict=True) if a != b)
    return {
        "seed": int(seed),
        "key": channels_cache_key(ch),
        "reference_key": channels_cache_key(ref),
        "n_days": int(n_days),
        "n_order_diffs": int(n_diff),
        "frac_order_diffs": float(n_diff / max(n_days, 1)),
        "max_abs_order_diff": int(max(diffs) if diffs else 0),
        "mean_abs_order_diff": float(sum(diffs) / len(diffs)) if diffs else 0.0,
    }

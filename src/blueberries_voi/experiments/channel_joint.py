"""Closed-loop channel-joint shards: belief accuracy + profit (notebook 19)."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

import numpy as np

from blueberries_voi.experiments.belief_accuracy import (
    day_distribution_abs_error,
    day_w1_error,
)
from blueberries_voi.experiments.filter_accuracy import PRESET_BY_KEY, day_accuracy
from blueberries_voi.experiments.voi_profit import (
    DEFAULT_FILTER_N,
    DEFAULT_N_BURN,
    DEFAULT_PROFIT_SEEDS,
    _channel_row,
    _damped_sw_act_kw,
    _day_log_from_delta,
    _resolve_controller_params,
    profit_session_config,
)
from blueberries_voi.filter.types import (
    ObsChannels,
    channels_cache_key,
    validate_channels,
)
from blueberries_voi.sim.profit import STUDIO_PROFIT_COSTS, ProfitCosts, day_profit
from blueberries_voi.simulator import EngineSession

CodeTypeOpt: TypeAlias = Literal["upc", "lgtin"]
WasteOpt: TypeAlias = Literal["off", "on"]
DeliveryOpt: TypeAlias = Literal["none", "pack_date", "temperature_history"]

CODE_OPTS: tuple[CodeTypeOpt, ...] = ("upc", "lgtin")
WASTE_OPTS: tuple[WasteOpt, ...] = ("off", "on")
DELIVERY_OPTS: tuple[DeliveryOpt, ...] = (
    "none",
    "pack_date",
    "temperature_history",
)

DEFAULT_N_SCORE = 30

__all__ = [
    "CODE_OPTS",
    "DEFAULT_N_BURN",
    "DEFAULT_N_SCORE",
    "DEFAULT_PROFIT_SEEDS",
    "DELIVERY_OPTS",
    "WASTE_OPTS",
    "all_obs_channels_product",
    "channel_joint_job_grid",
    "merge_channel_joint_rows",
    "obs_channels_product_labels",
    "run_seed_channel_joint",
]


def all_obs_channels_product() -> list[ObsChannels]:
    """Canonical 12-cell grid: code x waste x delivery history (nb19)."""
    out: list[ObsChannels] = []
    for code_type, scan_waste, delivery_history in itertools.product(
        CODE_OPTS,
        (False, True),
        DELIVERY_OPTS,
    ):
        out.append(
            ObsChannels(
                code_type=code_type,
                scan_waste=scan_waste,
                delivery_history=delivery_history,
            )
        )
    return out


def obs_channels_product_labels(
    channels: ObsChannels,
) -> tuple[CodeTypeOpt, WasteOpt, DeliveryOpt]:
    code: CodeTypeOpt = channels.code_type
    waste: WasteOpt = "on" if channels.scan_waste else "off"
    delivery: DeliveryOpt = channels.delivery_history
    return code, waste, delivery


def run_seed_channel_joint(
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
) -> dict[str, Any]:
    """One closed-loop episode: scored ``act()`` days yield MAE and profit."""
    ch = validate_channels(channels)
    use_costs = costs if costs is not None else STUDIO_PROFIT_COSTS
    alpha, rho = _resolve_controller_params(
        controller_alpha=controller_alpha,
        controller_rho=controller_rho,
        bo_json_path=bo_json_path,
        alpha_table_path=alpha_table_path,
    )

    session = EngineSession()
    cfg = profit_session_config(
        n_rollout_paths=n_rollout_paths,
        filter_n=filter_n,
        alpha_table_path=alpha_table_path,
    )
    session.init(cfg, seed=seed)
    session.set_obs_channels(ch)

    act_kw = _damped_sw_act_kw(alpha, rho, n_rollout_paths=n_rollout_paths)

    for _ in range(n_burn):
        session.act(**act_kw)

    profit = 0.0
    waste = 0
    stockout = 0
    f_errors: list[float] = []
    dist_errors: list[float] = []
    w1_errors: list[float] = []
    count_errors: list[float] = []
    filter_collapse_days = 0
    prev_belief_key: tuple[Any, ...] | None = None

    for day_idx in range(n_score):
        delta = session.act(**act_kw)
        episode_day = n_burn + day_idx
        log = _day_log_from_delta(episode_day, delta)
        profit += day_profit(log, use_costs)
        waste += log.waste_total
        stockout += max(0, log.demand - log.sales_total)

        # A collapsed filter freezes lot_counts/f_marginals bit-for-bit even as
        # real inventory depletes (2026-08-30 LGTIN collapse). A single day of
        # `infeasible == filter_n` is a normal, transient likelihood failure
        # under LGTIN's cross-lot approximation and recovers on its own — it is
        # not itself evidence of the freeze bug, so it is not counted here.
        belief = delta.get("belief")
        if isinstance(belief, dict):
            belief_key = (
                tuple(belief.get("lot_counts", ())),
                tuple(belief.get("f_marginals", ())),
            )
            depleted = (log.sales_total + log.waste_total) > 0
            frozen = prev_belief_key is not None and belief_key == prev_belief_key
            if depleted and frozen:
                filter_collapse_days += 1
            prev_belief_key = belief_key

        acc = day_accuracy(delta, episode_day)
        if acc is not None:
            f_errors.append(acc.abs_f_err)
            count_errors.append(acc.count_gap)
        dist = day_distribution_abs_error(delta)
        if dist is not None:
            dist_errors.append(dist)
        w1 = day_w1_error(delta)
        if w1 is not None:
            w1_errors.append(w1)

    row = _channel_row(
        seed,
        ch,
        profit=profit,
        waste=waste,
        stockout=stockout,
    )
    code, waste_label, delivery = obs_channels_product_labels(ch)
    row["waste_total"] = row.pop("waste")
    row.update(
        {
            "code_type": code,
            "waste": waste_label,
            "delivery": delivery,
            "mae_f": float(np.mean(f_errors)) if f_errors else float("nan"),
            "mae_dist": float(np.mean(dist_errors)) if dist_errors else float("nan"),
            "freshness_w1": float(np.mean(w1_errors)) if w1_errors else float("nan"),
            "count_mae": float(np.mean(count_errors)) if count_errors else float("nan"),
            "n_burn": int(n_burn),
            "n_score": int(n_score),
            "n_live_days": len(f_errors),
            "filter_collapse_days": int(filter_collapse_days),
        }
    )
    key = channels_cache_key(ch)
    row["preset"] = PRESET_BY_KEY.get(key, "custom")
    return row


def channel_joint_job_grid(
    seeds: tuple[int, ...],
    channels: Sequence[ObsChannels] | None = None,
) -> list[tuple[int, ObsChannels]]:
    chans = list(channels) if channels is not None else all_obs_channels_product()
    return [
        (int(seed), validate_channels(ch))
        for seed, ch in itertools.product(seeds, chans)
    ]


def merge_channel_joint_rows(shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

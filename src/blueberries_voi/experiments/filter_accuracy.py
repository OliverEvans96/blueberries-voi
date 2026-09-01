"""Batch job helpers for notebook 13 filter-accuracy channel factorial."""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass
from typing import Any, Literal, TypeAlias

import numpy as np

from blueberries_voi.filter.types import (
    ObsChannels,
    channels_cache_key,
    channels_for_preset,
    validate_channels,
)
from blueberries_voi.sim.shipments import default_shipments
from blueberries_voi.simulator import DEMO_BUDGETS, EngineSession
from blueberries_voi.voi import VOI_SCENARIOS

PosOpt: TypeAlias = Literal["upc_only", "lot_id"]
WasteOpt: TypeAlias = Literal["none", "daily_counts", "lot_id"]
DeliveryOpt: TypeAlias = Literal[
    "quantity_only", "pack_date_per_lot", "temperature_history"
]

POS_OPTS: tuple[PosOpt, ...] = ("upc_only", "lot_id")
WASTE_OPTS: tuple[WasteOpt, ...] = ("none", "daily_counts", "lot_id")
DEL_OPTS: tuple[DeliveryOpt, ...] = ("quantity_only", "pack_date_per_lot")

DEFAULT_SEEDS: tuple[int, ...] = (42, 7, 99)
DEFAULT_N_DAYS = 30
ETA_REF = 14.0

FILTER_SCENARIOS = tuple(s for s in VOI_SCENARIOS if s != "B-state")
PRESET_BY_KEY: dict[str, str] = {
    channels_cache_key(channels_for_preset(sid)): sid for sid in FILTER_SCENARIOS
}
# F3 is on the Rust obs ladder (temperature trace) but not in VOI_SCENARIOS.
PRESET_BY_KEY[channels_cache_key(channels_for_preset("F3"))] = "F3"
NAMED_LADDER: tuple[str, ...] = ("P0", "P1", "F1", "F1s", "F2a", "F2", "F3")


@dataclass(frozen=True)
class DayAccuracy:
    episode_day: int
    on_hand: int
    truth_f: float
    belief_f: float
    abs_f_err: float
    abs_age_err: float
    spread: float
    count_gap: float
    waste_total: int
    sales_total: int
    order_qty: int


def channel_from_factorial(
    pos: PosOpt,
    waste: WasteOpt,
    deliveries: DeliveryOpt,
) -> ObsChannels:
    """Map notebook 13 factorial axes to ``ObsChannels`` (ADR 0133)."""
    code_type: Literal["upc", "lgtin"] = "lgtin" if pos == "lot_id" else "upc"
    scan_waste = waste != "none"
    delivery_history: Literal["none", "pack_date", "temperature_history"] = (
        "pack_date" if deliveries == "pack_date_per_lot" else "none"
    )
    return ObsChannels(
        code_type=code_type,
        scan_waste=scan_waste,
        delivery_history=delivery_history,
    )


def all_channel_combos() -> list[ObsChannels]:
    """12 independent channel combinations (notebook 13 § channel factorial)."""
    return [
        channel_from_factorial(pos, waste, deliveries)
        for pos, waste, deliveries in itertools.product(POS_OPTS, WASTE_OPTS, DEL_OPTS)
    ]


def factorial_labels(channels: ObsChannels) -> tuple[PosOpt, WasteOpt, DeliveryOpt]:
    pos: PosOpt = "lot_id" if channels.code_type == "lgtin" else "upc_only"
    if not channels.scan_waste:
        waste: WasteOpt = "none"
    elif channels.code_type == "lgtin":
        waste = "lot_id"
    else:
        waste = "daily_counts"
    deliveries: DeliveryOpt
    if channels.delivery_history == "temperature_history":
        deliveries = "temperature_history"
    elif channels.delivery_history == "pack_date":
        deliveries = "pack_date_per_lot"
    else:
        deliveries = "quantity_only"
    return pos, waste, deliveries


def session_config_base(*, n_rollout_paths: int = 0) -> dict[str, Any]:
    """Damped-SW / filter-only budgets for accuracy studies (nb13)."""
    return {
        "shipments": default_shipments(),
        "n_particles": int(DEMO_BUDGETS["n_particles"]),
        "H": int(DEMO_BUDGETS["H"]),
        "n_rollout_paths": int(n_rollout_paths),
        "candidate_case_radius": int(DEMO_BUDGETS["candidate_case_radius"]),
        "L": 3,
        "K": 30,
        "enable_filter": True,
        "lead_time": 1,
        "obs_scenario": "P0",
    }


def _shelf_mean_f_from_live(live_lots: list[dict[str, Any]]) -> float | None:
    on_hand = sum(int(lot["n"]) for lot in live_lots)
    if on_hand <= 0:
        return None
    return sum(int(lot["n"]) * float(lot["mean_f"]) for lot in live_lots) / on_hand


def _shelf_mean_f_from_belief(belief: dict[str, Any]) -> float | None:
    counts = np.asarray(belief["lot_counts"], dtype=float)
    total = float(counts.sum())
    if total <= 0:
        return None
    grid = np.asarray(belief["f_grid"], dtype=float)
    k = len(grid)
    margs = np.asarray(belief["f_marginals"], dtype=float).reshape(int(belief["L"]), k)
    e_f = (margs * grid).sum(axis=1)
    return float((counts * e_f).sum() / total)


def _shelf_f_spread(belief: dict[str, Any]) -> float:
    counts = np.asarray(belief["lot_counts"], dtype=float)
    total = float(counts.sum())
    grid = np.asarray(belief["f_grid"], dtype=float)
    k = len(grid)
    margs = np.asarray(belief["f_marginals"], dtype=float).reshape(int(belief["L"]), k)
    mix = np.zeros(k, dtype=float)
    if total <= 0:
        return 0.0
    for ell in range(int(belief["L"])):
        w = counts[ell] / total
        row = margs[ell]
        rs = float(row.sum())
        if rs > 0:
            mix += w * (row / rs)
    s = float(mix.sum())
    if s > 0:
        mix /= s
    mean = float((grid * mix).sum())
    var = float(((grid - mean) ** 2 * mix).sum())
    return float(np.sqrt(max(var, 0.0)))


def day_accuracy(delta: dict[str, Any], episode_day: int) -> DayAccuracy | None:
    live = delta["live_lots"]
    belief = delta["belief"]
    on_hand = sum(int(lot["n"]) for lot in live)
    truth_f = _shelf_mean_f_from_live(live)
    belief_f = _shelf_mean_f_from_belief(belief)
    if truth_f is None or belief_f is None:
        return None
    day = delta["day"]
    return DayAccuracy(
        episode_day=episode_day,
        on_hand=on_hand,
        truth_f=truth_f,
        belief_f=belief_f,
        abs_f_err=abs(belief_f - truth_f),
        abs_age_err=abs((1 - belief_f) - (1 - truth_f)) * ETA_REF,
        spread=_shelf_f_spread(belief),
        count_gap=abs(float(sum(belief["lot_counts"])) - on_hand),
        waste_total=int(day["waste_total"]),
        sales_total=int(day["sales_total"]),
        order_qty=int(day["order_qty"]),
    )


def record_reference_path(
    seed: int,
    *,
    horizon: int,
    reference: str = "P0",
) -> tuple[list[int], list[list[dict[str, Any]]]]:
    session = EngineSession()
    cfg = session_config_base()
    cfg["obs_scenario"] = reference
    session.init(cfg, seed=seed)
    orders: list[int] = []
    truth_lots: list[list[dict[str, Any]]] = []
    for _day in range(horizon):
        delta = session.act()
        orders.append(int(delta["day"]["order_qty"]))
        truth_lots.append(delta["live_lots"])
    return orders, truth_lots


def replay_channels(
    channels: ObsChannels,
    seed: int,
    orders: list[int],
    truth_lots: list[list[dict[str, Any]]],
) -> list[DayAccuracy]:
    session = EngineSession()
    session.init(session_config_base(), seed=seed)
    session.set_obs_channels(channels)
    rows: list[DayAccuracy] = []
    for day, qty in enumerate(orders):
        delta = session.step(qty)
        if delta["live_lots"] != truth_lots[day]:
            key = channels_cache_key(channels)
            msg = f"physics diverged: {key} day {day}"
            raise RuntimeError(msg)
        row = day_accuracy(delta, day)
        if row is not None:
            rows.append(row)
    return rows


def run_seed_channel(
    seed: int,
    channel: ObsChannels | dict[str, object],
    *,
    n_days: int = DEFAULT_N_DAYS,
) -> dict[str, Any]:
    """One independent nb13 cell: shared P0 orders, sequential days, one channel."""
    ch = validate_channels(channel)
    orders, truth_lots = record_reference_path(seed, horizon=n_days)
    days = replay_channels(ch, seed, orders, truth_lots)
    key = channels_cache_key(ch)
    pos, waste, deliveries = factorial_labels(ch)
    mae_f = float(np.mean([d.abs_f_err for d in days])) if days else float("nan")
    mean_spread = float(np.mean([d.spread for d in days])) if days else float("nan")
    return {
        "seed": seed,
        "key": key,
        "pos": pos,
        "waste": waste,
        "deliveries": deliveries,
        "preset": PRESET_BY_KEY.get(key, "custom"),
        "mae_f": mae_f,
        "mean_spread": mean_spread,
        "n_days": n_days,
        "n_live_days": len(days),
        "days": [asdict(d) for d in days],
    }


def nb13_job_grid(
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    channels: list[ObsChannels] | None = None,
) -> list[tuple[int, ObsChannels]]:
    chans = all_channel_combos() if channels is None else channels
    return [(seed, ch) for seed in seeds for ch in chans]


def nb13_job_grid_with_f3(
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
) -> list[tuple[int, ObsChannels]]:
    """12-channel factorial plus named F3 (temperature history) per seed."""
    grid = nb13_job_grid(seeds=seeds)
    extra = [(seed, channels_for_preset("F3")) for seed in seeds]
    return grid + extra


def merge_channel_rows(shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge shard dicts from ``run_seed_channel`` (identity on unique cells)."""
    seen: set[tuple[int, str]] = set()
    out: list[dict[str, Any]] = []
    for shard in shards:
        key = (int(shard["seed"]), str(shard["key"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "seed": int(shard["seed"]),
                "key": str(shard["key"]),
                "pos": shard["pos"],
                "waste": shard["waste"],
                "deliveries": shard["deliveries"],
                "preset": str(shard["preset"]),
                "mae_f": float(shard["mae_f"]),
                "mean_spread": float(shard["mean_spread"]),
            }
        )
    return sorted(out, key=lambda r: (r["key"], r["seed"]))

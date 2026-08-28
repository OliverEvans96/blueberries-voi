"""Local ProcessPoolExecutor drivers (no Modal account required)."""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blueberries_voi.filter.types import ObsChannels


from blueberries_voi.experiments.batch_progress import log_grid_progress, log_line
from blueberries_voi.experiments.channel_joint import (
    channel_joint_job_grid,
    merge_channel_joint_rows,
    run_seed_channel_joint,
)
from blueberries_voi.experiments.controller_bakeoff import (
    controller_bakeoff_job_grid,
    merge_controller_bakeoff_rows,
)
from blueberries_voi.experiments.filter_accuracy import (
    DEFAULT_N_DAYS,
    DEFAULT_SEEDS,
    merge_channel_rows,
    nb13_job_grid,
)
from blueberries_voi.experiments.gsin_upc import (
    gsin_job_grid,
    merge_gsin_diag_rows,
)
from blueberries_voi.experiments.rollout_bakeoff import (
    merge_rollout_eval_rows,
    rollout_eval_job_grid,
    run_rollout_eval,
)
from blueberries_voi.experiments.voi_profit import (
    merge_voi_profit_rows,
    run_seed_channel_profit,
    run_seed_oracle_profit,
    voi_profit_job_grid,
)


def _nb13_worker(args: tuple[int, dict[str, object], int, int]) -> dict[str, Any]:
    seed, channel, n_days, job_index = args
    from blueberries_voi.experiments.batch_progress import log_nb13_done, log_nb13_start
    from blueberries_voi.experiments.filter_accuracy import run_seed_channel
    from blueberries_voi.filter.types import validate_channels

    ch = validate_channels(channel)
    t0 = log_nb13_start(seed, channel, job_index=job_index)
    result = run_seed_channel(seed, ch, n_days=n_days)
    result["_elapsed_s"] = log_nb13_done(seed, channel, t0, job_index=job_index)
    return result


def run_nb13_local(
    out_path: Path,
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    n_days: int = DEFAULT_N_DAYS,
    channels: list[ObsChannels] | None = None,
    max_workers: int | None = None,
) -> list[dict[str, Any]]:
    grid = nb13_job_grid(seeds=seeds, channels=channels)
    tasks = [(seed, ch.__dict__, n_days, i) for i, (seed, ch) in enumerate(grid)]
    total = len(tasks)
    log_line(f"nb13 local run: {total} jobs, days={n_days}, workers={max_workers}")
    shards: list[dict[str, Any]] = []
    completed = 0
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_nb13_worker, task) for task in tasks]
        for fut in as_completed(futures):
            shard = fut.result()
            shard.pop("_elapsed_s", None)
            shards.append(shard)
            completed += 1
            log_grid_progress(completed, total)
    rows = merge_channel_rows(shards)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows


def _gsin_worker(args: tuple[int, int]) -> dict[str, Any]:
    regime_index, seed_index = args
    from blueberries_voi.experiments.gsin_upc import run_regime_seed

    return run_regime_seed(regime_index, seed_index)


def run_gsin_local(
    out_path: Path,
    *,
    grid: list[tuple[int, int]] | None = None,
    max_workers: int | None = None,
) -> list[dict[str, Any]]:
    cells = gsin_job_grid() if grid is None else grid
    shards: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_gsin_worker, cell) for cell in cells]
        for fut in as_completed(futures):
            shards.append(fut.result())
    rows = merge_gsin_diag_rows(shards)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows


def _voi_profit_worker(
    args: tuple[int, dict[str, object], dict[str, Any]],
) -> dict[str, Any]:
    seed, channel, budgets = args
    return run_seed_channel_profit(seed, channel, **budgets)


def _voi_oracle_worker(args: tuple[int, dict[str, Any]]) -> dict[str, Any]:
    seed, budgets = args
    return run_seed_oracle_profit(seed, **budgets)


def run_voi_profit_local(
    out_path: Path,
    *,
    seeds: tuple[int, ...],
    channels: list[ObsChannels],
    include_oracle: bool = False,
    budgets: dict[str, Any] | None = None,
    max_workers: int | None = None,
    progress: bool = True,
) -> list[dict[str, Any]]:
    budget_kw = dict(budgets or {})
    budget_kw.pop("max_workers", None)
    budget_kw.pop("include_oracle", None)
    budget_kw.pop("seeds", None)
    budget_kw.pop("channels", None)
    grid = voi_profit_job_grid(seeds, channels)
    channel_tasks = [(seed, ch.__dict__, budget_kw) for seed, ch in grid]
    oracle_tasks = [(seed, budget_kw) for seed in seeds] if include_oracle else []
    total = len(channel_tasks) + len(oracle_tasks)
    log_line(f"voi_profit local run: {total} jobs, workers={max_workers}")
    shards: list[dict[str, Any]] = []
    completed = 0
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_voi_profit_worker, task) for task in channel_tasks]
        futures.extend(pool.submit(_voi_oracle_worker, task) for task in oracle_tasks)
        for fut in as_completed(futures):
            shards.append(fut.result())
            completed += 1
            if progress:
                log_grid_progress(completed, total)
    rows = merge_voi_profit_rows(shards)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows


def _channel_joint_worker(
    args: tuple[int, dict[str, object], dict[str, Any]],
) -> dict[str, Any]:
    seed, channel, budgets = args
    from blueberries_voi.experiments.batch_progress import (
        log_channel_joint_done,
        log_channel_joint_start,
    )

    t0 = log_channel_joint_start(seed, channel)
    result = run_seed_channel_joint(seed, channel, **budgets)
    result["_elapsed_s"] = log_channel_joint_done(seed, channel, t0)
    return result


def run_channel_joint_local(
    out_path: Path,
    *,
    seeds: tuple[int, ...],
    channels: list[ObsChannels],
    budgets: dict[str, Any] | None = None,
    max_workers: int | None = None,
    progress: bool = True,
) -> list[dict[str, Any]]:
    budget_kw = dict(budgets or {})
    for key in ("max_workers", "seeds", "channels", "progress"):
        budget_kw.pop(key, None)
    grid = channel_joint_job_grid(seeds, channels)
    tasks = [(seed, ch.__dict__, budget_kw) for seed, ch in grid]
    total = len(tasks)
    log_line(f"channel_joint local run: {total} jobs, workers={max_workers}")
    shards: list[dict[str, Any]] = []
    completed = 0
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_channel_joint_worker, task) for task in tasks]
        for fut in as_completed(futures):
            shard = fut.result()
            shard.pop("_elapsed_s", None)
            shards.append(shard)
            completed += 1
            if progress:
                log_grid_progress(completed, total, label="channel_joint")
    rows = merge_channel_joint_rows(shards)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows


def _rollout_eval_worker(
    args: tuple[int, str, float, float, dict[str, Any]],
) -> dict[str, Any]:
    seed, arm_id, alpha, rho, budgets = args
    return run_rollout_eval(seed, arm_id, alpha, rho, **budgets)


def run_rollout_eval_local(
    out_path: Path,
    *,
    seeds: tuple[int, ...],
    arms: tuple[str, ...],
    alphas: tuple[float, ...],
    rho: float,
    budgets: dict[str, Any] | None = None,
    max_workers: int | None = None,
    progress: bool = True,
) -> list[dict[str, Any]]:
    budget_kw = dict(budgets or {})
    for key in ("max_workers", "seeds", "arms", "alphas", "rho"):
        budget_kw.pop(key, None)
    grid = rollout_eval_job_grid(seeds, arms, alphas, rho)
    tasks = [(seed, arm, alpha, rho, budget_kw) for seed, arm, alpha, rho in grid]
    total = len(tasks)
    log_line(f"rollout_eval local run: {total} jobs, workers={max_workers}")
    shards: list[dict[str, Any]] = []
    completed = 0
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_rollout_eval_worker, task) for task in tasks]
        for fut in as_completed(futures):
            shards.append(fut.result())
            completed += 1
            if progress:
                log_grid_progress(completed, total)
    rows = merge_rollout_eval_rows(shards)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows


def _controller_bakeoff_worker(
    args: tuple[int, str, float, dict[str, Any]],
) -> dict[str, Any]:
    seed, arm_id, rho, budgets = args
    from blueberries_voi.experiments.controller_bakeoff import run_controller_eval

    kw = dict(budgets)
    belief_world = str(kw.pop("belief_world", "oracle"))
    kw.pop("rho", None)
    return run_controller_eval(
        seed,
        arm_id,
        float(rho),
        belief_world=belief_world,
        **kw,
    )


def run_controller_bakeoff_local(
    out_path: Path,
    *,
    seeds: tuple[int, ...],
    arms: tuple[str, ...],
    rho: float,
    budgets: dict[str, Any] | None = None,
    max_workers: int | None = None,
    progress: bool = True,
) -> list[dict[str, Any]]:
    budget_kw = dict(budgets or {})
    for key in ("max_workers", "seeds", "arms", "rho", "progress"):
        budget_kw.pop(key, None)
    budget_kw.setdefault("belief_world", "oracle")
    grid = controller_bakeoff_job_grid(seeds, arms, rho)
    tasks = [(seed, arm, arm_rho, dict(budget_kw)) for seed, arm, arm_rho in grid]
    total = len(tasks)
    log_line(f"controller_bakeoff local run: {total} jobs, workers={max_workers}")
    shards: list[dict[str, Any]] = []
    completed = 0
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_controller_bakeoff_worker, task) for task in tasks]
        for fut in as_completed(futures):
            shards.append(fut.result())
            completed += 1
            if progress:
                log_grid_progress(completed, total, label="controller_bakeoff")
    rows = merge_controller_bakeoff_rows(shards)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Local batch map drivers (T-155)")
    sub = parser.add_subparsers(dest="job", required=True)
    nb13 = sub.add_parser("nb13", help="Notebook 13 channel factorial")
    nb13.add_argument("out", type=Path)
    nb13.add_argument("--days", type=int, default=DEFAULT_N_DAYS)
    nb13.add_argument("--workers", type=int, default=None)
    gsin = sub.add_parser("gsin", help="gsin_upc_diag shard merge")
    gsin.add_argument("out", type=Path)
    gsin.add_argument("--workers", type=int, default=None)
    opts = parser.parse_args()
    if opts.job == "nb13":
        run_nb13_local(opts.out, n_days=opts.days, max_workers=opts.workers)
    else:
        run_gsin_local(opts.out, max_workers=opts.workers)

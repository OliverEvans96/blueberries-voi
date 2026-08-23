"""Local ProcessPoolExecutor drivers (no Modal account required)."""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from blueberries_voi.experiments.batch_progress import log_grid_progress, log_line
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
    max_workers: int | None = None,
) -> list[dict[str, Any]]:
    grid = nb13_job_grid(seeds=seeds)
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
    max_workers: int | None = None,
) -> list[dict[str, Any]]:
    grid = gsin_job_grid()
    shards: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_gsin_worker, cell) for cell in grid]
        for fut in as_completed(futures):
            shards.append(fut.result())
    rows = merge_gsin_diag_rows(shards)
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

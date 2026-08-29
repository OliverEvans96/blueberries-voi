"""Notebook batch dispatcher: Modal shards or local ProcessPoolExecutor."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal, assert_never

from tqdm.auto import tqdm

from blueberries_voi.experiments.batch_progress import log_line
from blueberries_voi.experiments.channel_joint import (
    DEFAULT_N_BURN as JOINT_N_BURN,
)
from blueberries_voi.experiments.channel_joint import (
    DEFAULT_N_SCORE as JOINT_N_SCORE,
)
from blueberries_voi.experiments.channel_joint import (
    all_obs_channels_product,
    channel_joint_job_grid,
    merge_channel_joint_rows,
)
from blueberries_voi.experiments.filter_accuracy import (
    DEFAULT_N_DAYS,
    DEFAULT_SEEDS,
    merge_channel_rows,
    nb13_job_grid,
    nb13_job_grid_with_f3,
)
from blueberries_voi.experiments.gsin_upc import gsin_job_grid, merge_gsin_diag_rows
from blueberries_voi.experiments.rollout_bakeoff import (
    DEFAULT_DESKTOP_ALPHAS,
    DEFAULT_RHO,
    DEFAULT_ROLLOUT_SEEDS,
    merge_rollout_eval_rows,
    rollout_eval_job_grid,
)
from blueberries_voi.experiments.rollout_bakeoff import (
    DEFAULT_N_BURN as ROLLOUT_N_BURN,
)
from blueberries_voi.experiments.rollout_bakeoff import (
    DEFAULT_N_SCORE as ROLLOUT_N_SCORE,
)
from blueberries_voi.experiments.voi_profit import (
    DEFAULT_N_BURN,
    DEFAULT_N_SCORE,
    DEFAULT_PROFIT_SEEDS,
    merge_voi_profit_rows,
    voi_profit_job_grid,
)
from blueberries_voi.filter.types import (
    ObsChannels,
    channels_for_preset,
    validate_channels,
)

BatchMode = Literal["modal", "local"]
BatchJob = Literal["nb13", "gsin", "voi_profit", "rollout_eval", "channel_joint"]

__all__ = ["BatchJob", "BatchMode", "run_batch"]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _ensure_repo_on_path() -> None:
    root = str(_REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _write_optional_json(rows: list[dict[str, Any]], out_path: Path | None) -> None:
    if out_path is None:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def _smoke_channels(channels: list[ObsChannels] | None) -> list[ObsChannels]:
    if channels:
        return [validate_channels(channels[0])]
    return [channels_for_preset("P0")]


def _smoke_seeds(seeds: tuple[int, ...]) -> tuple[int, ...]:
    return (int(seeds[0]),)


def run_batch(
    job: BatchJob,
    mode: BatchMode = "modal",
    *,
    out_path: Path | None = None,
    progress: bool = True,
    smoke: bool = False,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Dispatch a batch job to Modal or the local ProcessPoolExecutor."""
    if mode == "local":
        return _run_local(
            job, out_path=out_path, progress=progress, smoke=smoke, **kwargs
        )
    return _run_modal(job, out_path=out_path, progress=progress, smoke=smoke, **kwargs)


def _run_local(
    job: BatchJob,
    *,
    out_path: Path | None,
    progress: bool,
    smoke: bool,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    _ensure_repo_on_path()
    from experiments.modal import local_runner

    if job == "nb13":
        seeds = kwargs.get("seeds", DEFAULT_SEEDS)
        n_days = int(kwargs.get("n_days", DEFAULT_N_DAYS))
        channels = kwargs.get("channels")
        if smoke:
            seeds = _smoke_seeds(tuple(seeds))
            n_days = min(n_days, 3)
        rows = local_runner.run_nb13_local(
            out_path or Path("/tmp/nb13_rows.json"),
            seeds=tuple(seeds),
            n_days=n_days,
            channels=list(channels) if channels is not None else None,
            max_workers=kwargs.get("max_workers"),
        )
        return rows

    if job == "gsin":
        gsin_cells = kwargs.get("gsin_cells")
        if gsin_cells is not None:
            grid = [(int(r), int(s)) for r, s in gsin_cells]
        else:
            grid = gsin_job_grid()
        if smoke:
            grid = grid[:1]
        rows = local_runner.run_gsin_local(
            out_path or Path("/tmp/gsin_rows.json"),
            grid=grid,
            max_workers=kwargs.get("max_workers"),
        )
        return rows

    if job == "voi_profit":
        seeds = tuple(kwargs.get("seeds", DEFAULT_PROFIT_SEEDS))
        channels = list(kwargs.get("channels") or [])
        if not channels:
            msg = "run_batch('voi_profit') requires channels=..."
            raise ValueError(msg)
        if smoke:
            seeds = _smoke_seeds(seeds)
            channels = _smoke_channels(channels)
            kwargs = {
                **kwargs,
                "n_burn": min(int(kwargs.get("n_burn", DEFAULT_N_BURN)), 1),
                "n_score": min(int(kwargs.get("n_score", DEFAULT_N_SCORE)), 2),
            }
        rows = local_runner.run_voi_profit_local(
            out_path or Path("/tmp/voi_profit_rows.json"),
            seeds=seeds,
            channels=channels,
            include_oracle=bool(kwargs.get("include_oracle", False)),
            budgets=kwargs,
            max_workers=kwargs.get("max_workers"),
            progress=progress,
        )
        return rows

    if job == "rollout_eval":
        seeds = tuple(kwargs.get("seeds", DEFAULT_ROLLOUT_SEEDS))
        arms = tuple(kwargs.get("arms", ("sw", "rollout")))
        alphas = tuple(kwargs.get("alphas", DEFAULT_DESKTOP_ALPHAS))
        rho = float(kwargs.get("rho", DEFAULT_RHO))
        if smoke:
            seeds = _smoke_seeds(seeds)
            arms = (str(arms[0]),)
            alphas = (float(alphas[0]),)
        return local_runner.run_rollout_eval_local(
            out_path or Path("/tmp/rollout_eval_rows.json"),
            seeds=seeds,
            arms=arms,
            alphas=alphas,
            rho=rho,
            budgets=kwargs,
            max_workers=kwargs.get("max_workers"),
            progress=progress,
        )

    if job == "channel_joint":
        seeds = tuple(kwargs.get("seeds", DEFAULT_PROFIT_SEEDS))
        channels = list(kwargs.get("channels") or all_obs_channels_product())
        if smoke:
            seeds = _smoke_seeds(seeds)
            channels = _smoke_channels(channels)
            kwargs = {
                **kwargs,
                "n_burn": min(int(kwargs.get("n_burn", JOINT_N_BURN)), 1),
                "n_score": min(int(kwargs.get("n_score", JOINT_N_SCORE)), 2),
            }
        rows = local_runner.run_channel_joint_local(
            out_path or Path("/tmp/nb19_joint_rows.json"),
            seeds=seeds,
            channels=channels,
            budgets=kwargs,
            max_workers=kwargs.get("max_workers"),
            progress=progress,
        )
        return rows

    assert_never(job)


def _run_modal(
    job: BatchJob,
    *,
    out_path: Path | None,
    progress: bool,
    smoke: bool,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    import importlib

    _ensure_repo_on_path()
    try:
        app_mod = importlib.import_module("experiments.modal.app")
    except ImportError as exc:
        msg = (
            "Modal batch requires the modal extra: "
            "pip install 'blueberries-voi[modal]' or uv sync --extra modal"
        )
        raise RuntimeError(msg) from exc

    app = app_mod.app
    nb13_shard = app_mod.nb13_shard
    gsin_shard = app_mod.gsin_shard
    voi_profit_shard = app_mod.voi_profit_shard
    voi_oracle_profit_shard = app_mod.voi_oracle_profit_shard
    rollout_eval_shard = app_mod.rollout_eval_shard
    channel_joint_shard = app_mod.channel_joint_shard

    with app.run():
        if job == "nb13":
            seeds = kwargs.get("seeds", DEFAULT_SEEDS)
            n_days = int(kwargs.get("n_days", DEFAULT_N_DAYS))
            channels = kwargs.get("channels")
            if channels is not None:
                grid = nb13_job_grid(seeds=tuple(seeds), channels=list(channels))
            else:
                grid = nb13_job_grid_with_f3(seeds=tuple(seeds))
            if smoke:
                grid = grid[:1]
                n_days = min(n_days, 3)
            handles = [
                nb13_shard.spawn(seed, ch.__dict__, n_days, job_index=i)
                for i, (seed, ch) in enumerate(grid)
            ]
            shards = _collect_handles(handles, progress=progress)
            rows = merge_channel_rows(shards)
            _write_optional_json(rows, out_path)
            return rows

        if job == "gsin":
            raw_cells = kwargs.get("gsin_cells")
            if raw_cells is not None:
                gsin_cells = [(int(r), int(s)) for r, s in raw_cells]
            else:
                gsin_cells = gsin_job_grid()
            if smoke:
                gsin_cells = gsin_cells[:1]
            handles = [gsin_shard.spawn(regime, seed) for regime, seed in gsin_cells]
            shards = _collect_handles(handles, progress=progress)
            rows = merge_gsin_diag_rows(shards)
            _write_optional_json(rows, out_path)
            return rows

        if job == "voi_profit":
            seeds = tuple(kwargs.get("seeds", DEFAULT_PROFIT_SEEDS))
            channels = list(kwargs.get("channels") or [])
            if not channels:
                msg = "run_batch('voi_profit') requires channels=..."
                raise ValueError(msg)
            if smoke:
                seeds = _smoke_seeds(seeds)
                channels = _smoke_channels(channels)
            budgets = _voi_budgets_dict(kwargs, smoke=smoke)
            grid = voi_profit_job_grid(seeds, channels)
            handles = [
                voi_profit_shard.spawn(seed, ch.__dict__, budgets) for seed, ch in grid
            ]
            if bool(kwargs.get("include_oracle", False)):
                handles.extend(
                    voi_oracle_profit_shard.spawn(seed, budgets) for seed in seeds
                )
            shards = _collect_handles(handles, progress=progress)
            rows = merge_voi_profit_rows(shards)
            _write_optional_json(rows, out_path)
            return rows

        if job == "rollout_eval":
            seeds = tuple(kwargs.get("seeds", DEFAULT_ROLLOUT_SEEDS))
            arms = tuple(kwargs.get("arms", ("sw", "rollout")))
            alphas = tuple(kwargs.get("alphas", DEFAULT_DESKTOP_ALPHAS))
            rho = float(kwargs.get("rho", DEFAULT_RHO))
            if smoke:
                seeds = _smoke_seeds(seeds)
                arms = (str(arms[0]),)
                alphas = (float(alphas[0]),)
            budgets = _rollout_budgets_dict(kwargs, smoke=smoke)
            rollout_cells = rollout_eval_job_grid(seeds, arms, alphas, rho)
            handles = [
                rollout_eval_shard.spawn(seed, arm, alpha, rho_cell, budgets)
                for seed, arm, alpha, rho_cell in rollout_cells
            ]
            shards = _collect_handles(handles, progress=progress)
            rows = merge_rollout_eval_rows(shards)
            _write_optional_json(rows, out_path)
            return rows

        if job == "channel_joint":
            seeds = tuple(kwargs.get("seeds", DEFAULT_PROFIT_SEEDS))
            channels = list(kwargs.get("channels") or all_obs_channels_product())
            if smoke:
                seeds = _smoke_seeds(seeds)
                channels = _smoke_channels(channels)
            budgets = _channel_joint_budgets_dict(kwargs, smoke=smoke)
            grid = channel_joint_job_grid(seeds, channels)
            handles = [
                channel_joint_shard.spawn(seed, ch.__dict__, budgets)
                for seed, ch in grid
            ]
            shards = _collect_handles(handles, progress=progress)
            rows = merge_channel_joint_rows(shards)
            _write_optional_json(rows, out_path)
            return rows

    assert_never(job)


def _voi_budgets_dict(kwargs: dict[str, Any], *, smoke: bool) -> dict[str, Any]:
    n_burn = int(kwargs.get("n_burn", DEFAULT_N_BURN))
    n_score = int(kwargs.get("n_score", DEFAULT_N_SCORE))
    if smoke:
        n_burn = min(n_burn, 1)
        n_score = min(n_score, 2)
    return {
        "n_burn": n_burn,
        "n_score": n_score,
        "n_rollout_paths": int(kwargs.get("n_rollout_paths", 0)),
        "filter_n": int(kwargs.get("filter_n", 24)),
        "alpha_table_path": kwargs.get("alpha_table_path"),
        "controller_alpha": kwargs.get("controller_alpha"),
        "controller_rho": kwargs.get("controller_rho"),
        "bo_json_path": kwargs.get("bo_json_path"),
        "policy": kwargs.get("policy", "damped_sw"),
    }


def _channel_joint_budgets_dict(
    kwargs: dict[str, Any], *, smoke: bool
) -> dict[str, Any]:
    n_burn = int(kwargs.get("n_burn", JOINT_N_BURN))
    n_score = int(kwargs.get("n_score", JOINT_N_SCORE))
    if smoke:
        n_burn = min(n_burn, 1)
        n_score = min(n_score, 2)
    return {
        "n_burn": n_burn,
        "n_score": n_score,
        "n_rollout_paths": int(kwargs.get("n_rollout_paths", 0)),
        "filter_n": int(kwargs.get("filter_n", 24)),
        "alpha_table_path": kwargs.get("alpha_table_path"),
        "controller_alpha": kwargs.get("controller_alpha"),
        "controller_rho": kwargs.get("controller_rho"),
        "bo_json_path": kwargs.get("bo_json_path"),
    }


def _rollout_budgets_dict(kwargs: dict[str, Any], *, smoke: bool) -> dict[str, Any]:
    n_burn = int(kwargs.get("n_burn", ROLLOUT_N_BURN))
    n_score = int(kwargs.get("n_score", ROLLOUT_N_SCORE))
    if smoke:
        n_burn = min(n_burn, 2)
        n_score = min(n_score, 3)
    return {
        "n_burn": n_burn,
        "n_score": n_score,
        "rollout_h": int(kwargs.get("rollout_h", 28)),
        "n_rollout_paths": kwargs.get("n_rollout_paths"),
        "candidate_case_radius": kwargs.get("candidate_case_radius"),
    }


def _collect_handles(handles: list[Any], *, progress: bool) -> list[dict[str, Any]]:
    total = len(handles)
    if total == 0:
        return []
    if not progress:
        return [h.get() for h in handles]
    shards: list[dict[str, Any]] = []
    with (
        ThreadPoolExecutor(max_workers=min(32, total)) as pool,
        tqdm(total=total, desc="modal batch", unit="shard") as bar,
    ):
        futs = {pool.submit(h.get): i for i, h in enumerate(handles)}
        for fut in as_completed(futs):
            shard = fut.result()
            if isinstance(shard, dict):
                shard.pop("_elapsed_s", None)
            shards.append(shard)
            bar.update(1)
    log_line(f"modal batch collected {len(shards)} shards")
    return shards

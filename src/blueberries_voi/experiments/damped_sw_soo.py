"""damped_sw (alpha, rho) SOO shards for notebook 12 — Modal or local pools."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from statistics import mean, stdev
from typing import TYPE_CHECKING, Any

from blueberries_voi.model import ModelParams
from blueberries_voi.model.demand_profile import load_demand_profile
from blueberries_voi.sim.alpha_tune import evaluate_alpha_episode_outcomes
from blueberries_voi.sim.profit import ProfitCosts
from blueberries_voi.sim.shipments import default_shipments, smoke_cool_shipments

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

TUNE_ARM = "sw"


@dataclass(frozen=True)
class DampedSwSooBudgets:
    """Episode + economics bundle serialized into Modal shard jobs."""

    n_burn: int
    n_score: int
    lead_time: int
    unit_margin: float
    waste_cost: float
    stockout_penalty: float
    demand_mu: float
    demand_vm: float
    case_size: int
    use_calendar_demand: bool
    demand_profile_path: str
    use_abdella: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def replicate_mean_sem(values: Sequence[float]) -> tuple[float, float]:
    arr = list(values)
    if not arr:
        return 0.0, 0.0
    mu = float(mean(arr))
    if len(arr) < 2:
        return mu, 0.0
    return mu, float(stdev(arr) / (len(arr) ** 0.5))


def soo_job_payload(
    *,
    trial_index: int,
    alpha: float,
    rho: float,
    root_seed: int,
    budgets: DampedSwSooBudgets,
) -> dict[str, Any]:
    return {
        "trial_index": int(trial_index),
        "alpha": float(alpha),
        "rho": float(rho),
        "root_seed": int(root_seed),
        **budgets.to_dict(),
    }


def build_soo_jobs(
    trials: Mapping[int, Mapping[str, object]],
    seeds: Sequence[int],
    budgets: DampedSwSooBudgets,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for trial_index, params in trials.items():
        alpha = float(params["alpha"])
        rho = float(params["rho"])
        for seed in seeds:
            jobs.append(
                soo_job_payload(
                    trial_index=int(trial_index),
                    alpha=alpha,
                    rho=rho,
                    root_seed=int(seed),
                    budgets=budgets,
                )
            )
    return jobs


def _model_params_from_job(job: Mapping[str, Any]) -> ModelParams:
    profile = None
    if bool(job["use_calendar_demand"]):
        profile = load_demand_profile(str(job["demand_profile_path"]))
    return ModelParams(
        demand_mu=float(job["demand_mu"]),
        demand_vm=float(job["demand_vm"]),
        case_size=int(job["case_size"]),
        demand_profile=profile,
    )


def run_soo_shard(job: Mapping[str, Any]) -> dict[str, Any]:
    """Score one (trial, alpha, rho, seed) cell; safe for Modal workers."""
    t0 = time.perf_counter()
    try:
        params = _model_params_from_job(job)
        ships = (
            default_shipments() if bool(job["use_abdella"]) else smoke_cool_shipments()
        )
        costs = ProfitCosts(
            unit_margin=float(job["unit_margin"]),
            waste_cost=float(job["waste_cost"]),
            stockout_penalty=float(job["stockout_penalty"]),
        )
        out = evaluate_alpha_episode_outcomes(
            TUNE_ARM,
            float(job["alpha"]),
            int(job["root_seed"]),
            rho=float(job["rho"]),
            params=params,
            shipments=ships,
            costs=costs,
            n_burn=int(job["n_burn"]),
            n_score=int(job["n_score"]),
            lead_time=int(job["lead_time"]),
        )
        elapsed = time.perf_counter() - t0
        return {
            "trial_index": int(job["trial_index"]),
            "root_seed": int(job["root_seed"]),
            "alpha": float(job["alpha"]),
            "rho": float(job["rho"]),
            "ok": True,
            "profit": float(out.profit),
            "waste": int(out.total_waste),
            "stockout": int(out.total_lost_sales),
            "wall_s": float(elapsed),
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - shard diagnostics
        return {
            "trial_index": int(job["trial_index"]),
            "root_seed": int(job["root_seed"]),
            "alpha": float(job["alpha"]),
            "rho": float(job["rho"]),
            "ok": False,
            "profit": 0.0,
            "waste": 0,
            "stockout": 0,
            "wall_s": float(time.perf_counter() - t0),
            "error": str(exc),
        }


def aggregate_soo_shards(
    shards: Sequence[Mapping[str, Any]],
) -> dict[int, dict[str, tuple[float, float]]]:
    """Group flat shards by Ax trial → mean/SEM metrics for complete_trial."""
    by_trial: dict[int, list[Mapping[str, Any]]] = {}
    for shard in shards:
        if not bool(shard.get("ok", False)):
            tid = shard.get("trial_index")
            sid = shard.get("root_seed")
            err = shard.get("error")
            msg = f"shard failed trial={tid} seed={sid}: {err}"
            raise RuntimeError(msg)
        by_trial.setdefault(int(shard["trial_index"]), []).append(shard)

    out: dict[int, dict[str, tuple[float, float]]] = {}
    for trial_index, rows in by_trial.items():
        profits = [float(r["profit"]) for r in rows]
        wastes = [float(r["waste"]) for r in rows]
        stockouts = [float(r["stockout"]) for r in rows]
        out[trial_index] = {
            "episode_profit": replicate_mean_sem(profits),
            "total_waste": replicate_mean_sem(wastes),
            "total_stockout": replicate_mean_sem(stockouts),
        }
    return out


def evaluate_soo_jobs(
    jobs: list[dict[str, Any]],
    *,
    use_modal: bool = True,
    modal_concurrency: int = 32,
    local_max_workers: int | None = None,
) -> list[dict[str, Any]]:
    """Flat-pool evaluation: Modal (default) or local ProcessPoolExecutor."""
    if not jobs:
        return []

    if use_modal:
        import importlib

        from blueberries_voi.experiments.modal_dispatch import _ensure_repo_on_path

        _ensure_repo_on_path()
        try:
            app_mod = importlib.import_module("experiments.modal.app")
        except ImportError as exc:
            msg = "Modal extra required: uv sync --extra modal"
            raise RuntimeError(msg) from exc

        from concurrent.futures import ThreadPoolExecutor, as_completed

        shard_fn = app_mod.damped_sw_soo_shard
        app = app_mod.app
        cap = min(int(modal_concurrency), len(jobs))
        shards: list[dict[str, Any]] = []
        with app.run():
            for start in range(0, len(jobs), cap):
                chunk = jobs[start : start + cap]
                handles = [(job, shard_fn.spawn(job)) for job in chunk]
                with ThreadPoolExecutor(max_workers=len(handles)) as pool:
                    futs = {pool.submit(h.get): job for job, h in handles}
                    for fut in as_completed(futs):
                        shards.append(fut.result())
        return shards

    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    max_workers = local_max_workers or min(len(jobs), os.cpu_count() or 2)
    shards = []
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(run_soo_shard, job): job for job in jobs}
        for fut in as_completed(futs):
            shards.append(fut.result())
    return shards


__all__ = [
    "TUNE_ARM",
    "DampedSwSooBudgets",
    "aggregate_soo_shards",
    "build_soo_jobs",
    "evaluate_soo_jobs",
    "replicate_mean_sem",
    "run_soo_shard",
    "soo_job_payload",
]

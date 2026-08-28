#!/usr/bin/env python3
"""Ax BO scaffold for T-163 joint arrival calibration (p_short, q10, delta_c).

Writes ``outputs/arrival_joint_calib_bo.json``. Reload Ax state from
``outputs/arrival_joint_calib_bo_ax_client.json``.

Smoke: ``uv run python scripts/run_arrival_calib_bo.py --smoke``
Benchmark: ``uv run python scripts/run_arrival_calib_bo.py --benchmark``
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, cast

import numpy as np
from ax.api.client import Client
from tqdm.auto import tqdm

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.experiments.arrival_joint_calib import (
    AC2_11A_MIN_RATIO,
    REJECTED_OBJECTIVE,
    ax_outcome_constraints,
    ax_parameter_configs,
    benchmark_joint_calib_trial,
    evaluate_with_replicates,
    trial_passes_all_gates,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPO_ROOT)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

FULL_RUN = False
EXTRA_AX_TRIALS = 0
RELOAD_AX = False
AX_JSON = REPO_ROOT / "outputs" / "arrival_joint_calib_bo_ax_client.json"
OUTPUT_JSON = REPO_ROOT / "outputs" / "arrival_joint_calib_bo.json"
SEARCH_AX_JSON = REPO_ROOT / "outputs" / "arrival_joint_calib_search_ax_client.json"
SEARCH_OUTPUT_JSON = REPO_ROOT / "outputs" / "arrival_joint_calib_search_bo.json"

RNG = np.random.default_rng(20260828)


def _completed_trial_count(client: Client) -> int:
    return sum(1 for t in client._experiment.trials.values() if t.status.is_completed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="T-163 arrival joint Ax BO")
    parser.add_argument("--smoke", action="store_true", help="K=2, 10 trials, fast only")
    parser.add_argument("--full", action="store_true", help="60 trials, K=6, ac2_11a leg")
    parser.add_argument(
        "--search",
        action="store_true",
        help="10 trials/batch, up to 40 total, K=6, ac2_11a; stop when all gates pass",
    )
    parser.add_argument(
        "--benchmark", action="store_true", help="Time one fast trial and exit"
    )
    return parser.parse_args()


def resolve_run_config(args: argparse.Namespace) -> dict[str, Any]:
    if args.smoke:
        return {
            "full_run": False,
            "k_bo_seeds": 2,
            "total_ax_trials": 10,
            "ax_parallelism": 2,
            "include_ac2_11a": False,
        }
    if args.search:
        return {
            "full_run": False,
            "search_mode": True,
            "k_bo_seeds": 6,
            "total_ax_trials": 40,
            "batch_size": 10,
            "ax_parallelism": 10,
            "include_ac2_11a": True,
            "early_stop": True,
        }
    if args.full or FULL_RUN:
        return {
            "full_run": True,
            "search_mode": False,
            "k_bo_seeds": 6,
            "total_ax_trials": 60,
            "batch_size": 60,
            "ax_parallelism": 4,
            "include_ac2_11a": True,
            "early_stop": False,
        }
    return {
        "full_run": False,
        "search_mode": False,
        "k_bo_seeds": 2,
        "total_ax_trials": 10,
        "batch_size": 10,
        "ax_parallelism": 2,
        "include_ac2_11a": False,
        "early_stop": False,
    }


def main() -> None:
    args = parse_args()
    if args.benchmark:
        elapsed = benchmark_joint_calib_trial()
        print(json.dumps({"fast_metrics_s": elapsed}, indent=2))
        return

    cfg = resolve_run_config(args)
    ax_json = SEARCH_AX_JSON if cfg.get("search_mode") else AX_JSON
    output_json = SEARCH_OUTPUT_JSON if cfg.get("search_mode") else OUTPUT_JSON
    if cfg.get("search_mode"):
        for path in (ax_json, output_json):
            if path.is_file():
                path.unlink()
    bo_seeds = [
        int(RNG.integers(0, 2**31 - 1)) for _ in range(cfg["k_bo_seeds"])
    ]

    rust_fn = (
        getattr(rust_core, "evaluate_joint_calib_trial_py", None) if rust_core else None
    )
    print(
        f"T-163 joint arrival BO rust={rust_available() and rust_fn is not None} "
        f"trials={cfg['total_ax_trials']} batch={cfg.get('batch_size', cfg['total_ax_trials'])} "
        f"seeds={cfg['k_bo_seeds']} search={cfg.get('search_mode', False)} "
        f"slow={cfg['include_ac2_11a']}"
    )
    if not rust_available() or rust_fn is None:
        raise SystemExit(
            "build _core: uv run maturin develop --release "
            "-m crates/voi_py/Cargo.toml"
        )

    if RELOAD_AX and ax_json.is_file():
        client = Client.load_from_json_file(str(ax_json))
        completed = _completed_trial_count(client)
        trials_to_run = (
            EXTRA_AX_TRIALS
            if EXTRA_AX_TRIALS > 0
            else max(0, cfg["total_ax_trials"] - completed)
        )
        trial_log: list[dict[str, Any]] = []
        print(f"Reloaded Ax ({completed} completed); running {trials_to_run} more")
    else:
        client = Client()
        client.configure_experiment(
            name="t163-joint-arrival-calib-search"
            if cfg.get("search_mode")
            else "t163-joint-arrival-calib",
            parameters=ax_parameter_configs(),
        )
        client.configure_optimization(
            objective="ac2_11a_ratio",
            outcome_constraints=ax_outcome_constraints(),
        )
        trial_log = []
        trials_to_run = cfg["total_ax_trials"]

    completed = 0
    adequate_found = False
    batch_size = int(cfg.get("batch_size", trials_to_run))
    early_stop = bool(cfg.get("early_stop", False))
    pbar = tqdm(total=trials_to_run, desc="Ax joint arrival calib")
    while completed < trials_to_run and not adequate_found:
        batch_n = min(batch_size, trials_to_run - completed)
        trials = client.get_next_trials(max_trials=batch_n)
        for trial_index, parameters in trials.items():
            p_short = float(parameters["p_short"])
            q10 = float(parameters["q10"])
            delta_c = float(parameters["delta_c"])
            metrics = evaluate_with_replicates(
                p_short,
                q10,
                delta_c,
                bo_seeds,
                include_ac2_11a=cfg["include_ac2_11a"],
            )
            client.complete_trial(
                trial_index=trial_index,
                raw_data={
                    "ac2_11a_ratio": metrics["ac2_11a_ratio"],
                    "session_f": metrics["session_f"],
                    "p50": metrics["p50"],
                    "pct_60_90": metrics["pct_60_90"],
                },
            )
            rejected = margin <= 0.0 or session_mean <= REJECTED_OBJECTIVE / 2
            ac2_11a_mean = metrics["ac2_11a_ratio"][0]
            session_mean = metrics["session_f"][0]
            p50_mean = metrics["p50"][0]
            pct_mean = metrics["pct_60_90"][0]
            margin = metrics["ac2_19_margin"][0]
            passes_all = trial_passes_all_gates(
                rejected_ac2_19=rejected,
                ac2_19_margin=margin,
                session_f=session_mean,
                p50=p50_mean,
                pct_60_90=pct_mean,
                ac2_11a_ratio=ac2_11a_mean,
            )
            trial_log.append(
                {
                    "trial_index": int(trial_index),
                    "p_short": p_short,
                    "q10": q10,
                    "delta_c": delta_c,
                    "rejected_ac2_19": rejected,
                    "passes_all_gates": passes_all,
                    "mean_ac2_11a": ac2_11a_mean,
                    "sem_ac2_11a": metrics["ac2_11a_ratio"][1],
                    "session_f": session_mean,
                    "p50": p50_mean,
                    "pct_60_90": pct_mean,
                    "ac2_19_margin": margin,
                }
            )
            if passes_all:
                adequate_found = True
                print(
                    f"\nAll gates passed at trial {trial_index}: "
                    f"p_short={p_short:.4f} q10={q10:.3f} delta_c={delta_c:.3f} "
                    f"ac2_11a={ac2_11a_mean:.3f}"
                )
                if early_stop:
                    break
        ax_json.parent.mkdir(parents=True, exist_ok=True)
        client.save_to_json_file(str(ax_json))
        completed += len(trials)
        pbar.update(len(trials))
        if early_stop and adequate_found:
            break
    pbar.close()

    best_params, _pred, best_index, _name = client.get_best_parameterization()
    winners = [t for t in trial_log if t.get("passes_all_gates")]
    payload: dict[str, Any] = {
        "ticket": "T-163",
        "method": "ax_bo",
        "search_mode": cfg.get("search_mode", False),
        "full_run": cfg["full_run"],
        "include_ac2_11a": cfg["include_ac2_11a"],
        "total_ax_trials": cfg["total_ax_trials"],
        "trials_completed": len(trial_log),
        "batch_size": cfg.get("batch_size"),
        "early_stop": cfg.get("early_stop", False),
        "adequate_found": adequate_found,
        "ac2_11a_min_ratio": AC2_11A_MIN_RATIO,
        "bo_seeds": bo_seeds,
        "ax_client_path": str(ax_json.relative_to(REPO_ROOT)),
        "outcome_constraints": ax_outcome_constraints(),
        "best_trial_index": int(cast("int", best_index)),
        "best_params": {
            "p_short": float(best_params["p_short"]),
            "q10": float(best_params["q10"]),
            "delta_c": float(best_params["delta_c"]),
        },
        "all_gate_winners": winners,
        "search_space": {
            "p_short": [0.5, 0.9],
            "q10": [1.5, 3.0],
            "delta_c": [-3.0, 1.0],
        },
        "legacy_grid_examples": [
            "crates/voi_core/examples/t163_joint_fast_grid.rs",
            "crates/voi_core/examples/t163_joint_constraint_search.rs",
        ],
        "trials": trial_log,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_json}")
    print(f"Best trial {best_index}: {payload['best_params']}")
    if winners:
        print(f"All-gate winners ({len(winners)}): {winners[0]}")
    elif adequate_found:
        print("adequate_found set but winners list empty (check trial_log)")
    else:
        print(f"No trial passed all gates after {len(trial_log)} evaluations")


if __name__ == "__main__":
    main()

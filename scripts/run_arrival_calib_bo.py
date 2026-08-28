#!/usr/bin/env python3
"""Smoke/full Ax BO for T-163 joint arrival calibration (notebook 14 mirror).

Writes ``outputs/arrival_joint_calib_bo.json`` and persists Ax state to
``outputs/arrival_joint_calib_bo_ax_client.json``.

Grid examples ``t163_joint_fast_grid`` and ``t163_joint_constraint_search`` are
legacy diagnostics only — this script is the supported search path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import numpy as np
from ax.api.client import Client
from tqdm.auto import tqdm

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.experiments.arrival_joint_calib import (
    REJECTED_OBJECTIVE,
    ax_parameter_configs,
    evaluate_with_replicates,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPO_ROOT)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

FULL_RUN = False
if FULL_RUN:
    K_BO_SEEDS = 6
    TOTAL_AX_TRIALS = 60
    AX_PARALLELISM = 4
    INCLUDE_AC2_11A = True
else:
    K_BO_SEEDS = 2
    TOTAL_AX_TRIALS = 10
    AX_PARALLELISM = 2
    INCLUDE_AC2_11A = False

EXTRA_AX_TRIALS = 0
RELOAD_AX = False
AX_JSON = REPO_ROOT / "outputs" / "arrival_joint_calib_bo_ax_client.json"
OUTPUT_JSON = REPO_ROOT / "outputs" / "arrival_joint_calib_bo.json"

RNG = np.random.default_rng(20260828)
BO_SEEDS = [int(RNG.integers(0, 2**31 - 1)) for _ in range(K_BO_SEEDS)]


def _completed_trial_count(client: Client) -> int:
    return sum(1 for t in client._experiment.trials.values() if t.status.is_completed)


def main() -> None:
    rust_fn = (
        getattr(rust_core, "evaluate_joint_calib_trial_py", None) if rust_core else None
    )
    print(
        f"T-163 joint arrival BO rust={rust_available() and rust_fn is not None} "
        f"trials={TOTAL_AX_TRIALS} seeds={K_BO_SEEDS} full_run={FULL_RUN}"
    )
    if not rust_available() or rust_fn is None:
        raise SystemExit(
            "build _core: uv run maturin develop --release "
            "-m crates/voi_py/Cargo.toml"
        )

    if RELOAD_AX and AX_JSON.is_file():
        client = Client.load_from_json_file(str(AX_JSON))
        completed = _completed_trial_count(client)
        trials_to_run = (
            EXTRA_AX_TRIALS
            if EXTRA_AX_TRIALS > 0
            else max(0, TOTAL_AX_TRIALS - completed)
        )
        trial_log: list[dict[str, Any]] = []
        print(
            f"Reloaded Ax client ({completed} completed); "
            f"running {trials_to_run} more"
        )
    else:
        client = Client()
        client.configure_experiment(
            name="t163-joint-arrival-calib",
            parameters=ax_parameter_configs(),
        )
        client.configure_optimization(objective="session_f")
        trial_log = []
        trials_to_run = TOTAL_AX_TRIALS

    completed = 0
    pbar = tqdm(total=trials_to_run, desc="Ax joint arrival calib")
    while completed < trials_to_run:
        batch_n = min(AX_PARALLELISM, trials_to_run - completed)
        trials = client.get_next_trials(max_trials=batch_n)
        for trial_index, parameters in trials.items():
            p_short = float(parameters["p_short"])
            q10 = float(parameters["q10"])
            delta_c = float(parameters["delta_c"])
            metrics = evaluate_with_replicates(
                p_short,
                q10,
                delta_c,
                BO_SEEDS,
                include_ac2_11a=INCLUDE_AC2_11A,
            )
            client.complete_trial(
                trial_index=trial_index,
                raw_data={
                    "session_f": metrics["session_f"],
                    "p50": metrics["p50"],
                    "pct_60_90": metrics["pct_60_90"],
                    "ac2_19_margin": metrics["ac2_19_margin"],
                },
            )
            rejected = metrics["session_f"][0] <= REJECTED_OBJECTIVE / 2
            trial_log.append(
                {
                    "trial_index": int(trial_index),
                    "p_short": p_short,
                    "q10": q10,
                    "delta_c": delta_c,
                    "rejected_ac2_19": rejected,
                    "mean_session_f": metrics["session_f"][0],
                    "sem_session_f": metrics["session_f"][1],
                    "mean_p50": metrics["p50"][0],
                    "mean_pct_60_90": metrics["pct_60_90"][0],
                    "ac2_19_margin": metrics["ac2_19_margin"][0],
                    "mean_ac2_11a_ratio": metrics["ac2_11a_ratio"][0],
                }
            )
        AX_JSON.parent.mkdir(parents=True, exist_ok=True)
        client.save_to_json_file(str(AX_JSON))
        completed += len(trials)
        pbar.update(len(trials))
    pbar.close()

    best_params, _pred, best_index, _name = client.get_best_parameterization()
    payload: dict[str, Any] = {
        "ticket": "T-163",
        "method": "ax_bo",
        "full_run": FULL_RUN,
        "total_ax_trials": TOTAL_AX_TRIALS,
        "bo_seeds": BO_SEEDS,
        "ax_client_path": str(AX_JSON.relative_to(REPO_ROOT)),
        "best_trial_index": int(cast("int", best_index)),
        "best_params": {
            "p_short": float(best_params["p_short"]),
            "q10": float(best_params["q10"]),
            "delta_c": float(best_params["delta_c"]),
        },
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
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Best trial {best_index}: {payload['best_params']}")


if __name__ == "__main__":
    main()

"""Native compute matrix (py-native vs rust-pyo3). Browser columns via wasm-pack."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path


def _time(fn, repeats: int = 5) -> dict[str, float]:
    fn()
    xs = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        xs.append(time.perf_counter() - t0)
    xs.sort()
    return {
        "mean": sum(xs) / len(xs),
        "p50": xs[len(xs) // 2],
        "p95": xs[int(0.95 * (len(xs) - 1))],
        "n": repeats,
        "crossings": 1,
    }


def main() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    from blueberries_voi.model.day_step import day_step

    from blueberries_voi.model.params import Cohort, ModelParams
    from blueberries_voi.rng import STREAM_ALLOC, STREAM_SPOIL, spawn_rng
    from blueberries_voi.sim.shipments import smoke_cool_shipments
    from blueberries_voi.voi import run_voi_crn_cell

    params = ModelParams()
    ships = smoke_cool_shipments()
    matrix: dict[str, dict[str, object]] = {}

    def one_day() -> None:
        day_step(
            [Cohort(n=10, tau=0.0, lot_id=1)],
            params=params,
            demand=3,
            rng_alloc=spawn_rng(1, run_id="b", day=0, stream=STREAM_ALLOC),
            rng_spoil=spawn_rng(1, run_id="b", day=0, stream=STREAM_SPOIL),
        )

    def smoke_voi() -> None:
        run_voi_crn_cell(
            beta=2.0,
            root_seed=1,
            n_burn=1,
            n_score=2,
            filter_n=16,
            H=2,
            n_rollout_paths=1,
            shipments=ships,
        )

    os.environ["BLUEBERRIES_VOI_BACKEND"] = "python"
    matrix["py-native"] = {
        "day_step": _time(one_day, repeats=50),
        "smoke_voi": _time(smoke_voi, repeats=3),
    }
    os.environ["BLUEBERRIES_VOI_BACKEND"] = "rust"
    from blueberries_voi.backend import rust_available

    if rust_available():
        matrix["rust-pyo3"] = {
            "day_step": _time(one_day, repeats=50),
            "smoke_voi": _time(smoke_voi, repeats=3),
        }
    else:
        matrix["rust-pyo3"] = {
            "n/a": "maturin develop --manifest-path crates/voi_py/pyproject.toml"
        }
    matrix["pyodide"] = {
        "n/a": "browser worker; run experiments/bench_compute_browser.ts"
    }
    matrix["wasm"] = {"n/a": "./scripts/build-wasm.sh then VITE_ENGINE_ADAPTER=wasm"}
    matrix["meta"] = {
        "python": platform.python_version(),
        "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "cpu": platform.machine(),
    }
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/bench_compute_matrix.json").write_text(json.dumps(matrix, indent=2))
    print(json.dumps(matrix, indent=2))


if __name__ == "__main__":
    main()

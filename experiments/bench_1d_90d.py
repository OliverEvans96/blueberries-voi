"""Like-for-like 1-day vs 90-day EngineSession: Python vs release Rust/PyO3.

Interactive demo budgets (N=200, filter on). Headline 90-day cell is one
``step_n`` (one FFI crossing on Rust), not 90 Python-level ``step`` calls.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

N_PARTICLES = 200
H = 7
N_PATHS = 2
RADIUS = 1
SEED = 42
ORDER_QTY = 16  # one case-rounded studio-like order; not act/rollout
HORIZON = 90
REPEATS = 3
FIXED_QTY_1 = 16


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _cpu() -> str:
    try:
        out = subprocess.check_output(["lscpu"], text=True)
        for line in out.splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    return platform.processor() or platform.machine()


def _rustc_profile() -> dict[str, str]:
    info: dict[str, str] = {"requested": "release (maturin develop --release)"}
    try:
        info["rustc"] = subprocess.check_output(
            ["rustc", "--version"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        info["rustc"] = "unknown"
    try:
        from blueberries_voi.backend import rust_core

        so = getattr(rust_core, "__file__", None)
        info["extension"] = str(so) if so else "unknown"
    except Exception as exc:
        info["extension"] = f"unavailable: {exc}"
    return info


def _time(fn: Callable[[], Any], *, repeats: int = REPEATS) -> dict[str, float]:
    fn()  # warmup (discard)
    xs: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        xs.append(time.perf_counter() - t0)
    xs.sort()
    return {
        "mean_s": sum(xs) / len(xs),
        "min_s": xs[0],
        "max_s": xs[-1],
        "n": float(repeats),
    }


def _config() -> dict[str, Any]:
    from blueberries_voi.sim.shipments import smoke_cool_shipments
    from blueberries_voi.simulator import DEMO_BUDGETS

    assert int(DEMO_BUDGETS["n_particles"]) == N_PARTICLES
    return {
        "shipments": smoke_cool_shipments(),
        "n_particles": N_PARTICLES,
        "H": H,
        "n_rollout_paths": N_PATHS,
        "candidate_case_radius": RADIUS,
        "enable_filter": True,
        "lead_time": 1,
        "obs_scenario": "P1",
        "L": 2,
        "K": 4,
    }


def _session_fresh():
    from blueberries_voi.simulator import EngineSession

    sess = EngineSession()
    sess.init(_config(), seed=SEED)
    return sess


def _bench_engine(backend: str) -> dict[str, Any]:
    os.environ["BLUEBERRIES_VOI_BACKEND"] = backend
    from blueberries_voi.backend import rust_available

    if backend == "rust" and not rust_available():
        return {"error": "rust backend not importable; run maturin develop --release"}

    def one_day() -> None:
        sess = _session_fresh()
        sess.step(FIXED_QTY_1)

    def ninety_batched() -> None:
        sess = _session_fresh()
        deltas = sess.step_n([ORDER_QTY] * HORIZON)
        assert len(deltas) == HORIZON
        if backend == "rust":
            # init is one crossing; step_n must add exactly one more (not 90).
            assert sess.host_crossings() == 2, sess.host_crossings()

    def one_act() -> None:
        sess = _session_fresh()
        sess.act(policy="rollout")

    def ninety_act() -> None:
        # No act_n / in-Rust act loop on this tip: 90 host calls.
        sess = _session_fresh()
        crossings_before = sess.host_crossings() if backend == "rust" else 0
        for _ in range(HORIZON):
            sess.act(policy="rollout")
        if backend == "rust":
            assert sess.host_crossings() == crossings_before + HORIZON, (
                sess.host_crossings()
            )

    out: dict[str, Any] = {
        "simulator_1d_step": _time(one_day),
        "simulator_90d_step_n": _time(ninety_batched),
        "controller_1d_act_rollout": _time(one_act),
        "controller_90d_act_rollout": _time(ninety_act),
        "controller_90d_note": (
            "90x EngineSession.act(policy='rollout'); no act_n - "
            "Rust FFI crossings = 90 (plus init)"
        ),
        "backend_env": backend,
        "rust_available": rust_available() if backend == "rust" else False,
    }

    # Footnote: 90 naive step() calls (FFI per day on Rust). Same physics.
    def ninety_naive() -> None:
        sess = _session_fresh()
        for _ in range(HORIZON):
            sess.step(ORDER_QTY)

    out["footnote_90_naive_step"] = _time(ninety_naive)
    return out


def _bench_physics(backend: str) -> dict[str, Any]:
    """Filter-off day_step 1 vs 90 (clarifies physics vs RBPF cost)."""
    os.environ["BLUEBERRIES_VOI_BACKEND"] = backend
    from blueberries_voi.model.day_step import day_step
    from blueberries_voi.model.params import Cohort, ModelParams
    from blueberries_voi.rng import STREAM_ALLOC, STREAM_SPOIL, spawn_rng

    params = ModelParams()

    def one() -> None:
        day_step(
            [Cohort(n=10, tau=0.0, lot_id=1)],
            params=params,
            demand=3,
            rng_alloc=spawn_rng(1, run_id="b", day=0, stream=STREAM_ALLOC),
            rng_spoil=spawn_rng(1, run_id="b", day=0, stream=STREAM_SPOIL),
        )

    def ninety() -> None:
        cohorts = [Cohort(n=10, tau=0.0, lot_id=1)]
        for d in range(HORIZON):
            res = day_step(
                cohorts,
                params=params,
                demand=3,
                rng_alloc=spawn_rng(1, run_id="b", day=d, stream=STREAM_ALLOC),
                rng_spoil=spawn_rng(1, run_id="b", day=d, stream=STREAM_SPOIL),
            )
            cohorts = res.cohorts

    return {
        "1_day_step": _time(one, repeats=20),
        "90_day_step_python_loop": _time(ninety, repeats=5),
        "note": (
            "Rust cell still crosses PyO3 once per day_step (no Python "
            "advance_days binding). Headline matrix is EngineSession."
        ),
    }


def main() -> None:
    matrix: dict[str, Any] = {
        "meta": {
            "python": platform.python_version(),
            "sha": _git_sha(),
            "cpu": _cpu(),
            "machine": platform.machine(),
            "omp": os.environ.get("OMP_NUM_THREADS"),
            "openblas": os.environ.get("OPENBLAS_NUM_THREADS"),
            "rustc": _rustc_profile(),
            "fixture": "smoke_cool_shipments",
            "n_particles": N_PARTICLES,
            "enable_filter": True,
            "order_qty": ORDER_QTY,
            "horizon_days": HORIZON,
            "repeats": REPEATS,
            "policy": (
                "act(policy='rollout') on both backends (Rust act is rollout-only)"
            ),
        },
        "engine_session": {
            "python": _bench_engine("python"),
            "rust": _bench_engine("rust"),
        },
        "physics_only_day_step": {
            "python": _bench_physics("python"),
            "rust": _bench_physics("rust"),
        },
    }
    Path("outputs").mkdir(exist_ok=True)
    path = Path("outputs/bench_1d_90d_python_rust.json")
    path.write_text(json.dumps(matrix, indent=2) + "\n")
    print(json.dumps(matrix, indent=2))
    print(f"wrote {path}", flush=True)


if __name__ == "__main__":
    main()

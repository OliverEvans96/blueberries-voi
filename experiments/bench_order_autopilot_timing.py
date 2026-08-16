"""Order-click compute timing: native Rust example + PyO3 + optional WASM (Node).

Studio path: WASM worker `step` / `act` RPC (compute before UI render).
DEMO_BUDGETS: n_particles=200, H=7, n_rollout_paths=2, candidate_case_radius=1.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parents[1]
N_PARTICLES = 200
H = 7
N_PATHS = 2
RADIUS = 1
SEED = 42
ORDER_QTY = 16
ITERS = 30


def _percentiles(xs: list[float]) -> dict[str, float]:
    xs = sorted(xs)
    n = len(xs)
    return {
        "mean_ms": sum(xs) / n * 1000 if xs and xs[0] < 1 else sum(xs) / n,
        "p50_ms": xs[n // 2] * (1000 if xs[0] < 1 else 1),
        "p95_ms": xs[int(0.95 * (n - 1))] * (1000 if xs[0] < 1 else 1),
        "n": float(n),
    }


def _time_seconds(fn: Callable[[], Any], *, iters: int = ITERS) -> dict[str, float]:
    fn()
    xs: list[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        fn()
        xs.append(time.perf_counter() - t0)
    xs.sort()
    n = len(xs)
    return {
        "mean_ms": sum(xs) / n * 1000,
        "p50_ms": xs[n // 2] * 1000,
        "p95_ms": xs[int(0.95 * (n - 1))] * 1000,
        "n": float(n),
    }


def _config() -> dict[str, Any]:
    from blueberries_voi.sim.shipments import smoke_cool_shipments
    from blueberries_voi.simulator import DEMO_BUDGETS

    return {
        "shipments": smoke_cool_shipments(),
        "n_particles": int(DEMO_BUDGETS["n_particles"]),
        "H": int(DEMO_BUDGETS["H"]),
        "n_rollout_paths": int(DEMO_BUDGETS["n_rollout_paths"]),
        "candidate_case_radius": int(DEMO_BUDGETS["candidate_case_radius"]),
        "enable_filter": True,
        "lead_time": 1,
        "obs_scenario": "P1",
        "L": 2,
        "K": 4,
    }


def _warm_session():
    from blueberries_voi.simulator import EngineSession

    s = EngineSession()
    s.init(_config(), seed=SEED)
    for _ in range(3):
        s.step(ORDER_QTY)
    return s


def run_native_cargo() -> dict[str, Any]:
    cmd = [
        "cargo",
        "run",
        "--release",
        "--example",
        "bench_demo_session",
        "-q",
    ]
    env = {**os.environ, "OMP_NUM_THREADS": "1"}
    out = subprocess.check_output(cmd, cwd=ROOT, env=env, text=True)
    start = out.find("{")
    end = out.rfind("}") + 1
    return json.loads(out[start:end])


def run_pyo3_rust() -> dict[str, Any]:
    os.environ["BLUEBERRIES_VOI_BACKEND"] = "rust"
    return {
        "step_order": _time_seconds(lambda: _warm_session().step(ORDER_QTY)),
        "act_damped_sw": _time_seconds(
            lambda: _warm_session().act(policy="damped_sw")
        ),
        "act_rollout": _time_seconds(lambda: _warm_session().act(policy="rollout")),
    }


def run_wasm_node() -> dict[str, Any]:
    pkg = ROOT / "packaging/wasm/pkg/voi_wasm.js"
    if not pkg.is_file():
        return {"n_a": "missing packaging/wasm/pkg — run scripts/build-wasm.sh"}

    script = ROOT / "experiments/bench_wasm_order_timing.mjs"
    if not script.is_file():
        return {"n_a": "bench_wasm_order_timing.mjs missing"}
    out = subprocess.check_output(["node", str(script)], cwd=ROOT, text=True)
    return json.loads(out.strip().splitlines()[-1])


def autoplay_hz(mean_ms: float) -> float:
    return 1000.0 / mean_ms if mean_ms > 0 else 0.0


def main() -> None:
    native = run_native_cargo()
    pyo3 = run_pyo3_rust()
    wasm: dict[str, Any]
    try:
        wasm = run_wasm_node()
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        wasm = {"n_a": str(e)}

    payload = {
        "meta": {
            "cpu": platform.processor() or platform.machine(),
            "python": platform.python_version(),
            "omp": os.environ.get("OMP_NUM_THREADS"),
        },
        "native_rust_example": native,
        "pyo3_engine_session": pyo3,
        "wasm_node": wasm,
    }
    out_path = ROOT / "outputs/bench_order_autopilot_timing.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

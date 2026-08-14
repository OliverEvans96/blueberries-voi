"""Native compute matrix (py-native vs rust-pyo3). Browser columns later."""

from __future__ import annotations

import json
import os
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
    return {"mean": sum(xs) / len(xs), "p50": xs[len(xs) // 2], "p95": xs[int(0.95 * (len(xs) - 1))]}


def main() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    from blueberries_voi.model.day_step import day_step
    from blueberries_voi.model.params import Cohort, ModelParams
    from blueberries_voi.rng import STREAM_ALLOC, STREAM_SPOIL, spawn_rng

    params = ModelParams()

    def one_day() -> None:
        day_step(
            [Cohort(n=10, tau=0.0, lot_id=1)],
            params=params,
            demand=3,
            rng_alloc=spawn_rng(1, run_id="b", day=0, stream=STREAM_ALLOC),
            rng_spoil=spawn_rng(1, run_id="b", day=0, stream=STREAM_SPOIL),
        )

    row = _time(one_day, repeats=50)
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/bench_compute_matrix.json").write_text(json.dumps({"py-native": {"day_step": row}}, indent=2))
    print(row)


if __name__ == "__main__":
    main()

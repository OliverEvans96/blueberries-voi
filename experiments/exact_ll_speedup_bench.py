#!/usr/bin/env python3
"""T-066 exact LL speedup bench (OMP_NUM_THREADS=1).

Probes: sequential_wor_composition_probs, mean_field_update, closed-loop P1/F2a.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np

# Cap BLAS/OpenMP threads for reproducible wall times.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")


def _time_call(fn: Any, *args: Any, repeats: int = 3, **kwargs: Any) -> float:
    # Warmup
    fn(*args, **kwargs)
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn(*args, **kwargs)
        best = min(best, time.perf_counter() - t0)
    return best


def bench_dp() -> list[dict[str, Any]]:
    from blueberries_voi.filter.age_likelihood import sequential_wor_composition_probs

    grids = [
        ([8, 8], 12),
        ([8, 8, 8], 12),
        ([12, 12, 12], 18),
        ([16, 16, 16], 24),
        ([20, 20, 20], 30),
    ]
    rows: list[dict[str, Any]] = []
    for counts, sales in grids:
        w = np.ones(len(counts), dtype=float)
        wall = _time_call(sequential_wor_composition_probs, counts, sales, w, repeats=3)
        rows.append(
            {
                "counts": counts,
                "sales": sales,
                "wall_s": wall,
                "wall_ms": wall * 1e3,
            }
        )
    return rows


def bench_mf() -> list[dict[str, Any]]:
    from blueberries_voi.filter.age_likelihood import mean_field_update

    from blueberries_voi.filter.types import P1Obs, age_grid
    from blueberries_voi.model import ModelParams

    params = ModelParams()
    k = 8
    tau = age_grid(k)
    prior = np.ones((3, k), dtype=float) / k
    rows: list[dict[str, Any]] = []
    for counts, sales, waste in (
        ([8, 8, 8], 12, 2),
        ([12, 12, 12], 18, 3),
        ([16, 16, 16], 24, 4),
    ):
        y = P1Obs(sales_total=sales, waste_total=waste, arrivals=0)
        n = np.asarray(counts, dtype=int)

        def _run(
            n: np.ndarray = n,
            y: P1Obs = y,
            prior: np.ndarray = prior,
        ) -> None:
            mean_field_update(n, prior.copy(), y, params, tau_grid=tau, max_sweeps=2)

        wall = _time_call(_run, repeats=2)
        rows.append({"counts": counts, "sales": sales, "wall_s": wall})
    return rows


def bench_crn(*, scenarios: list[str]) -> list[dict[str, Any]]:
    from blueberries_voi.voi.crn import run_voi_crn_cell

    rows: list[dict[str, Any]] = []
    for name in scenarios:
        t0 = time.perf_counter()
        run_voi_crn_cell(
            beta=2.0,
            root_seed=7,
            scenarios=[name],
            n_burn=2,
            n_score=4,
            filter_n=16,
            H=2,
            n_rollout_paths=1,
        )
        wall = time.perf_counter() - t0
        rows.append({"scenario": name, "wall_s": wall, "per_day_s": wall / 6.0})
    return rows


def uniqueness_probe() -> dict[str, Any]:
    """Estimate unique-key hit rate on a short P1 episode (N=16)."""
    import blueberries_voi.filter.age_likelihood as age_likelihood
    import blueberries_voi.filter.backends as backends
    from blueberries_voi.filter.particle.research import ResearchParticleFilter

    from blueberries_voi.filter.types import UNOBSERVED, RichObs, mask_for
    from blueberries_voi.model import ModelParams

    real = age_likelihood.mean_field_update
    calls = 0
    unique_keys: set[tuple[Any, ...]] = set()

    def _spy(counts: Any, age_post: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        key = (tuple(np.asarray(counts).tolist()), np.asarray(age_post).tobytes())
        unique_keys.add(key)
        return real(counts, age_post, *args, **kwargs)

    age_likelihood.mean_field_update = _spy  # type: ignore[assignment]
    backends.mean_field_update = _spy  # type: ignore[attr-defined]

    particle_filter = ResearchParticleFilter(params=ModelParams(), N=16, K=8, L=3)
    rng = np.random.default_rng(0)
    particle_filter.initialize(rng)
    obs = mask_for("P1").apply(
        RichObs(
            arrivals=0,
            sales_total=8,
            waste_total=1,
            sales_by_lot={1: 8},
            waste_by_lot={1: 1},
            pack_date=UNOBSERVED,
            age_at_receipt=UNOBSERVED,
            lot_ids_live=UNOBSERVED,
        )
    )
    # Several days to accumulate resample duplicates.
    particle_days = 0
    for _ in range(6):
        assert particle_filter._state is not None
        particle_days += particle_filter.N
        particle_filter.step(obs, rng)

    return {
        "mf_calls": calls,
        "unique_keys_seen": len(unique_keys),
        "particle_days": particle_days,
        "calls_per_particle_day": calls / max(particle_days, 1),
        "note": "calls_per_particle_day < 1 implies dedup savings vs naive N/day",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="after", help="baseline|after|label")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/exact_ll_speedup_bench.json"),
    )
    parser.add_argument("--skip-crn", action="store_true")
    parser.add_argument("--skip-uniqueness", action="store_true")
    args = parser.parse_args()

    payload: dict[str, Any] = {
        "label": args.label,
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
        "dp": bench_dp(),
        "mean_field": bench_mf(),
    }
    if not args.skip_crn:
        payload["crn"] = bench_crn(scenarios=["P1", "F2a"])
    if not args.skip_uniqueness:
        payload["uniqueness"] = uniqueness_probe()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

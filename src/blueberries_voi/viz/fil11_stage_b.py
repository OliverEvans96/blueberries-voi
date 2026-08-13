"""FIL-11 Stage B calibration runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.filter import RBPF, P1Obs
from blueberries_voi.filter.rbpf import PRODUCTION_K, PRODUCTION_L, PRODUCTION_N
from blueberries_voi.filter.types import age_grid
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import run_episode
from blueberries_voi.viz.fil11_metrics import (
    FIG,
    ROOT,
    STAGE_B_COVERAGE_HI,
    STAGE_B_COVERAGE_LO,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class StageBResult:
    coverage_90: float
    n_reps: int
    n_particles: int
    K: int
    rank_mean: float
    rank_std: float
    figure_path: Path
    passed: bool


def run_fil11_stage_b(
    params: ModelParams | None = None,
    *,
    n_reps: int = 50,
    n_particles: int = PRODUCTION_N,
    K: int = PRODUCTION_K,
    L: int = PRODUCTION_L,
    n_burn: int = 10,
    n_score: int = 25,
    figures_dir: Path | None = None,
) -> StageBResult:
    """Calibration: 90% CI coverage + rank histogram (production mean_field).

    Diagnostic after Stage A fail — does not reopen the FIL-11=D gate.
    Smoke tests should pass small ``n_particles`` / ``n_score`` (MF age update
    is O(N) per day under ADR 0091).
    """
    import matplotlib.pyplot as plt

    p = params or ModelParams()
    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    out = figures_dir or FIG
    out.mkdir(parents=True, exist_ok=True)
    covers: list[bool] = []
    ranks: list[float] = []
    grid = age_grid(K)
    for rep in range(n_reps):
        ep = run_episode(
            p,
            root_seed=100 + rep,
            run_id=f"b{rep}",
            n_burn=n_burn,
            n_score=n_score,
            shipments=ships,
        )
        rbpf = RBPF(params=p, N=n_particles, K=K, L=L)
        rng = np.random.default_rng(100 + rep)
        rbpf.initialize(rng, L=L)
        true_age: float | None = None
        for d in ep.scored:
            if d.lots:
                # Youngest lot current tau (proxy for tracked cohort age).
                true_age = d.lots[-1].tau
            rbpf.step(P1Obs(d.sales_total, d.waste_total, d.arrivals), rng)
        # Prefer last slot (youngest) when available.
        post = rbpf.age_posterior(min(L - 1, rbpf.L - 1))
        cdf = np.cumsum(post)
        lo = float(grid[int(np.searchsorted(cdf, 0.05))])
        hi = float(grid[min(len(grid) - 1, int(np.searchsorted(cdf, 0.95)))])
        if true_age is None:
            true_age = float(np.mean(grid))
        true_clip = float(np.clip(true_age, grid[0], grid[-1]))
        covers.append(lo <= true_clip <= hi)
        ranks.append(float(np.interp(true_clip, grid, cdf)))

    coverage = float(np.mean(covers))
    rank_arr = np.asarray(ranks, dtype=float)
    rank_mean = float(rank_arr.mean()) if len(rank_arr) else 0.0
    rank_std = float(rank_arr.std(ddof=0)) if len(rank_arr) else 0.0
    passed = STAGE_B_COVERAGE_LO <= coverage <= STAGE_B_COVERAGE_HI
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(ranks, bins=10, range=(0, 1), color="#2a6f97", edgecolor="white")
    ax.axhline(n_reps / 10, color="k", ls="--", lw=1, label="uniform")
    ax.set_xlabel("Posterior rank of true age")
    ax.set_title(
        f"FIL-11 Stage B (diagnostic) - 90% CI coverage={coverage:.2f} "
        f"(N={n_particles}, K={K}, R={n_reps})"
    )
    ax.legend()
    fig.tight_layout()
    path = out / "fil11_calibration.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return StageBResult(
        coverage_90=coverage,
        n_reps=n_reps,
        n_particles=n_particles,
        K=K,
        rank_mean=rank_mean,
        rank_std=rank_std,
        figure_path=path,
        passed=passed,
    )

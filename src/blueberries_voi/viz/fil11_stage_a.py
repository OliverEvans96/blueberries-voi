"""FIL-11 Stage A contraction runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.filter import RBPF, P1Obs
from blueberries_voi.filter.types import age_grid
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import run_episode
from blueberries_voi.viz.fil11_metrics import (
    FIG,
    ROOT,
    _arrival_prior,
    _spread,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class StageAResult:
    contracted: bool
    prior_spread: float
    posterior_spread: float
    tight_posterior_spread: float
    figure_path: Path
    margin: float


def run_fil11_stage_a(
    params: ModelParams | None = None,
    *,
    spread_tight: float = 0.05,
    spread_full: float = 1.0,
    figures_dir: Path | None = None,
) -> StageAResult:
    """Contraction go/no-go using mix-specific arrival priors (FIL-11 Stage A)."""
    import matplotlib.pyplot as plt

    p = params or ModelParams()
    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    out = figures_dir or FIG
    out.mkdir(parents=True, exist_ok=True)
    K = 8
    grid = age_grid(K)
    prior_full = _arrival_prior(spread_full, K)
    prior_tight = _arrival_prior(spread_tight, K)

    def filter_with_prior(spread: float, prior: np.ndarray, seed: int) -> np.ndarray:
        ep = run_episode(
            p,
            root_seed=seed,
            run_id=f"a{spread}",
            n_burn=20,
            n_score=30,
            spread_scale=spread,
            shipments=ships,
        )
        rbpf = RBPF(params=p, N=500, K=K, L=3)
        rng = np.random.default_rng(seed)
        rbpf.initialize(rng, L=3)
        assert rbpf._state is not None
        rbpf._state.age_post[:] = prior[None, None, :]
        for d in ep.scored:
            rbpf.step(
                P1Obs(d.sales_total, d.waste_total, d.arrivals),
                rng,
            )
            # Re-seed new arrivals with the mix prior (not flat).
            if d.arrivals > 0 and rbpf._state is not None:
                rbpf._state.age_post[:, -1, :] = prior[None, :]
        return rbpf.age_posterior(0)

    post_full = filter_with_prior(spread_full, prior_full, 21)
    post_tight = filter_with_prior(spread_tight, prior_tight, 21)
    prior_s = _spread(prior_full, grid)
    post_full_s = _spread(post_full, grid)
    post_tight_s = _spread(post_tight, grid)
    prior_tight_s = _spread(prior_tight, grid)
    margin = 0.05

    # Full mix: posterior must contract vs its prior. Tight: little further contraction.
    full_contracted = post_full_s < prior_s * (1.0 - margin)
    tight_weak = post_tight_s >= prior_tight_s * (1.0 - margin) or (
        (prior_s - post_full_s) > (prior_tight_s - post_tight_s)
    )
    contracted = bool(full_contracted and tight_weak)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.plot(grid, prior_full, label=f"prior full (sigma={prior_s:.2f})", lw=2)
    ax.plot(grid, post_full, label=f"posterior full (sigma={post_full_s:.2f})", lw=2)
    ax.plot(
        grid,
        prior_tight,
        label=f"prior tight (sigma={prior_tight_s:.2f})",
        lw=1.5,
        ls=":",
    )
    ax.plot(
        grid,
        post_tight,
        label=f"posterior tight (sigma={post_tight_s:.2f})",
        lw=2,
        ls="--",
    )
    ax.set_xlabel("Arrival effective age (days)")
    ax.set_ylabel("Mass")
    status = "PASS" if contracted else "FAIL"
    ax.set_title(f"FIL-11 Stage A contraction - {status}")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = out / "fil11_contraction.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)

    return StageAResult(
        contracted=contracted,
        prior_spread=prior_s,
        posterior_spread=post_full_s,
        tight_posterior_spread=post_tight_s,
        figure_path=path,
        margin=margin,
    )

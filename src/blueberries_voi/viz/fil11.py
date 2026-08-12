"""FIL-11 staged validation helpers and Stage A/B/C runners."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from blueberries_voi.filter import RBPF, P1Obs
from blueberries_voi.filter.rbpf import PRODUCTION_K, PRODUCTION_L, PRODUCTION_N
from blueberries_voi.filter.types import age_grid
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import run_episode

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "figures" / "m1"

# Documented Stage B coverage band around nominal 90% (diagnostic, not gate).
STAGE_B_COVERAGE_LO = 0.70
STAGE_B_COVERAGE_HI = 0.99
STAGE_C_TV_TOL = 0.05


@dataclass
class StageAResult:
    contracted: bool
    prior_spread: float
    posterior_spread: float
    tight_posterior_spread: float
    figure_path: Path
    margin: float


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


@dataclass
class StageCResult:
    tv: float
    tvs: dict[int, float]
    L: int
    K: int
    figure_path: Path
    passed: bool


def _spread(post: np.ndarray, grid: np.ndarray) -> float:
    mean = float(np.sum(grid * post))
    var = float(np.sum(post * (grid - mean) ** 2))
    return float(np.sqrt(max(var, 0.0)))


def _arrival_prior(spread_scale: float, K: int, n_samples: int = 400) -> np.ndarray:
    """Discrete arrival-age prior under a given spread_scale (bootstrap mix)."""
    from blueberries_voi.model.abdella import shipment_arrival_age

    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    params = ModelParams()
    base = np.array(
        [shipment_arrival_age(s, q10=params.q10, t_ref_c=params.t_ref_c) for s in ships]
    )
    mean_age = float(base.mean())
    rng = np.random.default_rng(7)
    ages_a = mean_age + spread_scale * (rng.choice(base, size=n_samples) - mean_age)
    grid = age_grid(K)
    half = (grid[1] - grid[0]) / 2
    edges = np.concatenate(
        [[grid[0] - half], (grid[:-1] + grid[1:]) / 2, [grid[-1] + half]]
    )
    hist, _ = np.histogram(np.clip(ages_a, grid[0], grid[-1]), bins=edges)
    prior = hist.astype(float)
    return prior / max(float(prior.sum()), 1e-300)


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


def run_fil11_stage_b(
    params: ModelParams | None = None,
    *,
    n_reps: int = 50,
    n_particles: int = PRODUCTION_N,
    K: int = PRODUCTION_K,
    L: int = PRODUCTION_L,
    figures_dir: Path | None = None,
) -> StageBResult:
    """Calibration: 90% CI coverage + rank histogram (production full_joint).

    Diagnostic after Stage A fail — does not reopen the FIL-11=D gate.
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
            n_burn=10,
            n_score=25,
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


def run_fil11_stage_c(
    params: ModelParams | None = None,
    *,
    L: int | tuple[int, ...] = (2, 3),
    K: int = 4,
    figures_dir: Path | None = None,
) -> StageCResult:
    """Exact forward vs full_joint at small L/K (TV tol ~0.05).

    Diagnostic after Stage A fail — does not reopen the FIL-11=D gate.
    ``params`` reserved for API parity with Stage A/B; exact check uses shared
    kernels inside ``tv_vs_exact``.
    """
    import matplotlib.pyplot as plt

    from blueberries_voi.filter.backends import tv_vs_exact

    _ = params  # API parity; exact path embeds ModelParams defaults.
    out = figures_dir or FIG
    out.mkdir(parents=True, exist_ok=True)
    l_values: tuple[int, ...] = (L,) if isinstance(L, int) else tuple(L)
    tvs: dict[int, float] = {
        li: tv_vs_exact("full_joint", L=li, K=K) for li in l_values
    }
    tv = float(max(tvs.values())) if tvs else 0.0
    passed = all(v < STAGE_C_TV_TOL for v in tvs.values())
    labels = [f"L={li}" for li in l_values]
    vals = [tvs[li] for li in l_values]
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.bar(labels, vals, color="#264653")
    ax.axhline(STAGE_C_TV_TOL, color="r", ls="--", label=f"tol={STAGE_C_TV_TOL}")
    ax.set_ylim(0, max(0.1, tv * 1.4 + 0.01))
    ax.set_ylabel("TV vs exact")
    ax.set_title(
        f"FIL-11 Stage C (diagnostic) - K={K}, max TV={tv:.4f} "
        f"({'PASS' if passed else 'FAIL'})"
    )
    ax.legend()
    fig.tight_layout()
    path = out / "fil11_exact.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return StageCResult(
        tv=tv,
        tvs=tvs,
        L=l_values[-1] if l_values else 0,
        K=K,
        figure_path=path,
        passed=passed,
    )

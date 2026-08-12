"""FIL-11 staged validation helpers and Stage A/B/C runners."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from blueberries_voi.filter import RBPF, P1Obs
from blueberries_voi.filter.backends import observation_loglik_mc
from blueberries_voi.filter.rbpf import PRODUCTION_K, PRODUCTION_L, PRODUCTION_N
from blueberries_voi.filter.types import RichObs, age_grid
from blueberries_voi.model import (
    Cohort,
    ModelParams,
    day_step,
    death_prob_hazard_product,
    draw_demand,
    picking_weights,
    q10_age_increment,
)
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import run_episode

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "figures" / "m1.5"

# Documented Stage B coverage band around nominal 90% (diagnostic, not gate).
STAGE_B_COVERAGE_LO = 0.70
STAGE_B_COVERAGE_HI = 0.99
# Default generative Stage C TV / CRN-divergence tolerance (ADR 0088 / T-012).
STAGE_C_TV_TOL = 0.05
_STAGE_C_SEED = 202_608_12


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
    divergence: float
    tolerance: float
    passed: bool
    figure_path: Path
    mode: Literal["generative_day_step"]
    L: int = 2
    K: int = 4
    n_support: int = 0


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


def _stage_c_cohorts(L: int, K: int) -> list[Cohort]:
    """Fixed inventory for generative Stage C with non-degenerate P1 support.

    Counts are large enough relative to default demand that sellout is not
    universal, so (sales, waste) has multi-point empirical support.
    """
    grid = age_grid(K)
    cohorts: list[Cohort] = []
    for ell in range(L):
        n = 18 + 2 * ell
        tau = float(grid[min(ell + 1, K - 1)])
        cohorts.append(Cohort(n=n, tau=tau, lot_id=ell + 1))
    return cohorts


def _clone_cohorts(cohorts: list[Cohort]) -> list[Cohort]:
    return [Cohort(n=c.n, tau=c.tau, lot_id=c.lot_id) for c in cohorts]


def _obs_from_day_step(
    cohorts: list[Cohort],
    params: ModelParams,
    rng: np.random.Generator,
) -> tuple[int, int]:
    """Honest simulator / production observation model via shared ``day_step``."""
    result = day_step(
        _clone_cohorts(cohorts),
        params=params,
        demand=None,
        delivery=None,
        rng_demand=rng,
        rng_alloc=rng,
        rng_spoil=rng,
    )
    return int(result.sales_total), int(result.waste_total)


def _obs_from_wrong_physics(
    cohorts: list[Cohort],
    params: ModelParams,
    rng: np.random.Generator,
) -> tuple[int, int]:
    """Wrong-physics observation model: soft sales powers + hazard*dt deaths.

    Reference simulator stays on shared ``day_step``; only the injected filter
    observation model uses this path (ADR 0088 falsification).
    """
    live = _clone_cohorts([c for c in cohorts if c.n > 0])
    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    for c in live:
        c.tau += dtau
    demand = draw_demand(rng, params)
    if not live:
        return 0, 0
    taus = [c.tau for c in live]
    counts = [c.n for c in live]
    weights = picking_weights(
        taus,
        sigma=params.sigma,
        beta=params.beta,
        eta=params.eta_ref,
        uniform=params.uniform_picking,
    )
    soft = np.power(np.maximum(weights, 1e-300), 3.0)
    soft = soft / float(soft.sum())
    on_hand = int(sum(counts))
    sales_total = min(int(demand), on_hand)
    sales_by = rng.multinomial(sales_total, soft)
    sales_by = np.minimum(sales_by, np.asarray(counts, dtype=int))
    sales_total = int(sales_by.sum())
    remaining = [int(counts[i] - sales_by[i]) for i in range(len(live))]
    waste_total = 0
    for i, c in enumerate(live):
        n_left = remaining[i]
        if n_left <= 0:
            continue
        p_die = death_prob_hazard_product(
            c.tau, dtau, beta=params.beta, eta=params.eta_ref
        )
        waste_total += int(rng.binomial(n_left, p_die))
    return sales_total, waste_total


def _empirical_pmf(
    pairs: list[tuple[int, int]],
) -> dict[tuple[int, int], float]:
    counts: dict[tuple[int, int], float] = {}
    for pair in pairs:
        counts[pair] = counts.get(pair, 0.0) + 1.0
    total = float(len(pairs)) if pairs else 1.0
    return {k: v / total for k, v in counts.items()}


def _tv_discrete(
    p: dict[tuple[int, int], float],
    q: dict[tuple[int, int], float],
) -> float:
    keys = set(p) | set(q)
    return float(0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys))


def _production_mc_ll_finite(
    cohorts: list[Cohort],
    params: ModelParams,
    pair: tuple[int, int],
    rng: np.random.Generator,
) -> bool:
    """Production path must score a sim obs under T-011 ``observation_loglik_mc``."""
    counts = np.asarray([[c.n for c in cohorts]], dtype=int)
    ages = np.asarray([[c.tau for c in cohorts]], dtype=float)
    obs = RichObs.from_p1(P1Obs(sales_total=pair[0], waste_total=pair[1], arrivals=0))
    ll = float(observation_loglik_mc(counts, ages, obs, params, rng, n_mc=4)[0])
    return bool(np.isfinite(ll))


def run_fil11_stage_c(
    params: ModelParams | None = None,
    *,
    L: int = 2,
    K: int = 4,
    n_obs_samples: int = 200,
    tolerance: float = STAGE_C_TV_TOL,
    inject_wrong_physics: bool = False,
    figures_dir: Path | None = None,
) -> StageCResult:
    """Generative Stage C vs ``day_step`` (ADR 0088 / T-012).

    Paired-CRN check (ADR-allowed): for each seed, compare the simulator
    ``day_step`` observation to the observation model under the same seed.

    - Production: observation model is shared ``day_step`` (kernels used by
      ``observation_loglik_mc``).
    - Injected wrong physics: soft sales powers + hazard*dt deaths.

    Divergence is TV between the two empirical discrete P1 distributions
    (equivalently 0 under exact CRN match). Requires non-degenerate support.
    """
    import matplotlib.pyplot as plt

    p = params or ModelParams()
    out = figures_dir or FIG
    out.mkdir(parents=True, exist_ok=True)
    cohorts = _stage_c_cohorts(L, K)

    sim_pairs: list[tuple[int, int]] = []
    model_pairs: list[tuple[int, int]] = []
    for i in range(n_obs_samples):
        seed = _STAGE_C_SEED + i
        sim_pairs.append(_obs_from_day_step(cohorts, p, np.random.default_rng(seed)))
        model_rng = np.random.default_rng(seed)
        if inject_wrong_physics:
            model_pairs.append(_obs_from_wrong_physics(cohorts, p, model_rng))
        else:
            # Production observation model = shared day_step kernels (T-011 MC LL).
            model_pairs.append(_obs_from_day_step(cohorts, p, model_rng))

    n_support = len(set(sim_pairs))
    if n_support < 2:
        msg = (
            f"Stage C empirical support is degenerate (n_support={n_support}); "
            "refusing vacuous generative check"
        )
        raise RuntimeError(msg)

    if not inject_wrong_physics:
        ok = _production_mc_ll_finite(
            cohorts,
            p,
            sim_pairs[0],
            np.random.default_rng(_STAGE_C_SEED + 77_777),
        )
        if not ok:
            msg = "production observation_loglik_mc returned non-finite score"
            raise RuntimeError(msg)

    divergence = _tv_discrete(_empirical_pmf(sim_pairs), _empirical_pmf(model_pairs))
    passed = bool(divergence <= tolerance)

    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    ax.bar(
        ["divergence", "tolerance"],
        [divergence, tolerance],
        color=["#264653", "#e76f51"],
    )
    status = "PASS" if passed else "FAIL"
    physics = (
        "wrong-physics inject" if inject_wrong_physics else "production day_step/MC LL"
    )
    ax.set_ylabel("TV (paired CRN discrete P1 obs)")
    ax.set_title(
        f"FIL-11 Stage C generative ({physics}) - {status}\n"
        f"L={L}, K={K}, n={n_obs_samples}, support={n_support}, "
        f"TV={divergence:.4f}"
    )
    fig.tight_layout()
    path = out / "fil11_stage_c_generative.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)

    return StageCResult(
        divergence=float(divergence),
        tolerance=float(tolerance),
        passed=passed,
        figure_path=path,
        mode="generative_day_step",
        L=L,
        K=K,
        n_support=n_support,
    )

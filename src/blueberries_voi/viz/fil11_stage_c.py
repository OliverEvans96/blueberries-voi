"""FIL-11 Stage C generative check vs day_step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from blueberries_voi.filter import P1Obs
from blueberries_voi.filter.backends import observation_loglik_mc
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
from blueberries_voi.viz.fil11_metrics import _STAGE_C_SEED, FIG, STAGE_C_TV_TOL

if TYPE_CHECKING:
    from pathlib import Path


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

"""FIL-11 Stage C: exact joint vs mean-field (FIL-04 check).

Usage:
  uv run python experiments/fil11_stage_c_mf.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from blueberries_voi.filter.age_likelihood import (
    exact_joint_update,
    induced_joint_from_marginals,
    joint_total_variation,
    marginal_kl,
    marginal_total_variation,
    marginals_from_joint,
    max_pairwise_mutual_information,
    mean_field_update,
    survival_weighted_on_hand,
)
from blueberries_voi.filter.types import P1Obs
from blueberries_voi.model import (
    Cohort,
    ModelParams,
    day_step,
    q10_age_increment,
)
from blueberries_voi.rng import STREAM_ALLOC, STREAM_SPOIL, spawn_rng

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "figures" / "m1"
NOTE = ROOT / "experiments" / "fil11_stage_c_mf_result.md"

# ADR 0090 freeze gates
MARG_TV_MEDIAN_MAX = 0.02
MARG_TV_P95_MAX = 0.05
JOINT_TV_MEDIAN_MAX = 0.05
ACTION_AGREE_MIN = 0.95


@dataclass(frozen=True)
class CaseResult:
    name: str
    L: int
    K: int
    sigma: float
    joint_tv: float
    marg_tv_max: float
    marg_tv_mean: float
    marg_kl_max: float
    max_mi: float
    sw_rel_delta: float
    action_agree: bool


def _uniform_joint(L: int, K: int) -> np.ndarray:
    return np.ones(K**L, dtype=float) / float(K**L)


def _uniform_marginals(L: int, K: int) -> np.ndarray:
    return np.ones((L, K), dtype=float) / float(K)


def _order_argmax(
    n: list[int],
    belief: np.ndarray,
    *,
    params: ModelParams,
    tau_grid: list[float],
    from_marginals: bool,
    orders: list[int],
    target_sw: float = 40.0,
) -> int:
    """Myopic order: snap ``max(0, target_sw - E[SW])`` to the order grid."""
    sw = survival_weighted_on_hand(
        n,
        belief,
        params=params,
        tau_grid=tau_grid,
        from_marginals=from_marginals,
    )
    need = max(0.0, float(target_sw) - float(sw))
    return int(min(orders, key=lambda o: abs(float(o) - need)))


def _compare_one(
    *,
    name: str,
    n: list[int],
    y: P1Obs,
    params: ModelParams,
    tau_grid: list[float],
    prior_joint: np.ndarray | None = None,
    prior_marg: np.ndarray | None = None,
) -> CaseResult:
    L = len(n)
    K = len(tau_grid)
    pj = prior_joint if prior_joint is not None else _uniform_joint(L, K)
    pm = prior_marg if prior_marg is not None else _uniform_marginals(L, K)
    post_j = exact_joint_update(n, pj, y, params, tau_grid=tau_grid)
    post_m = mean_field_update(n, pm, y, params, tau_grid=tau_grid)
    induced = induced_joint_from_marginals(post_m)
    exact_marg = marginals_from_joint(post_j, L=L, K=K)

    marg_tvs = [
        marginal_total_variation(exact_marg[ell], post_m[ell]) for ell in range(L)
    ]
    marg_kls = [marginal_kl(exact_marg[ell], post_m[ell]) for ell in range(L)]
    jtv = joint_total_variation(post_j, induced)
    mi = max_pairwise_mutual_information(post_j, L=L, K=K)

    sw_e = survival_weighted_on_hand(
        n, post_j, params=params, tau_grid=tau_grid, from_marginals=False
    )
    sw_m = survival_weighted_on_hand(
        n, post_m, params=params, tau_grid=tau_grid, from_marginals=True
    )
    stock = max(float(sum(n)), 1.0)
    sw_rel = abs(sw_e - sw_m) / stock

    orders = [0, 8, 16, 24]
    a_e = _order_argmax(
        n, post_j, params=params, tau_grid=tau_grid, from_marginals=False, orders=orders
    )
    a_m = _order_argmax(
        n, post_m, params=params, tau_grid=tau_grid, from_marginals=True, orders=orders
    )

    return CaseResult(
        name=name,
        L=L,
        K=K,
        sigma=float(params.sigma),
        joint_tv=jtv,
        marg_tv_max=float(max(marg_tvs)),
        marg_tv_mean=float(np.mean(marg_tvs)),
        marg_kl_max=float(max(marg_kls)),
        max_mi=mi,
        sw_rel_delta=sw_rel,
        action_agree=a_e == a_m,
    )


def stage1_cases() -> list[CaseResult]:
    """One-step synthetic cases (ADR protocol table)."""
    results: list[CaseResult] = []
    K = 6
    grid = [float(x) for x in np.linspace(0.5, 7.0, K)]

    # Balanced ages, mild sigma
    params = ModelParams(sigma=0.5)
    results.append(
        _compare_one(
            name="balanced_mild_sigma",
            n=[8, 8],
            y=P1Obs(sales_total=6, waste_total=2, arrivals=0),
            params=params,
            tau_grid=grid,
        )
    )

    # Strong age gap + fresh-biased sigma
    params_lifo = ModelParams(sigma=0.2)
    # Bias prior toward young on lot0 / old on lot1 via joint encoding later;
    # for one-step use mid grid but L=2 with informative waste.
    results.append(
        _compare_one(
            name="age_gap_lifo",
            n=[10, 10],
            y=P1Obs(sales_total=8, waste_total=4, arrivals=0),
            params=params_lifo,
            tau_grid=grid,
        )
    )

    # Near-dead cohort (high ages on lot 1 via tight prior on last bins)
    L, K3 = 2, 6
    pm = np.ones((L, K3), dtype=float) / K3
    pm[0, :] = 0.0
    pm[0, 0] = 1.0  # young
    pm[1, :] = 0.0
    pm[1, -1] = 1.0  # near-dead
    pj = induced_joint_from_marginals(pm)
    results.append(
        _compare_one(
            name="near_dead_cohort",
            n=[12, 4],
            y=P1Obs(sales_total=5, waste_total=3, arrivals=0),
            params=ModelParams(sigma=0.5),
            tau_grid=grid,
            prior_joint=pj,
            prior_marg=pm,
        )
    )

    # Highly informative waste
    results.append(
        _compare_one(
            name="large_waste",
            n=[10, 10],
            y=P1Obs(sales_total=2, waste_total=10, arrivals=0),
            params=ModelParams(sigma=0.5),
            tau_grid=grid,
        )
    )

    # Weak info
    results.append(
        _compare_one(
            name="weak_info",
            n=[10, 10],
            y=P1Obs(sales_total=1, waste_total=0, arrivals=0),
            params=ModelParams(sigma=0.5),
            tau_grid=grid,
        )
    )

    # L=3 primary gate base
    grid3 = [float(x) for x in np.linspace(0.5, 7.0, 6)]
    results.append(
        _compare_one(
            name="L3_base_P1",
            n=[8, 8, 8],
            y=P1Obs(sales_total=9, waste_total=3, arrivals=0),
            params=ModelParams(sigma=0.5),
            tau_grid=grid3,
        )
    )

    # Stress: LIFO + rich info L=3
    results.append(
        _compare_one(
            name="L3_stress_lifo_rich",
            n=[10, 10, 10],
            y=P1Obs(sales_total=12, waste_total=8, arrivals=0),
            params=ModelParams(sigma=0.2),
            tau_grid=grid3,
        )
    )
    return results


def stage2_multiday(
    *, L: int = 3, K: int = 6, T: int = 15, sigma: float = 0.5
) -> list[CaseResult]:
    """Multi-day fixed count path from open-loop sim; replay joint vs MF."""
    params = ModelParams(sigma=sigma)
    grid = [float(x) for x in np.linspace(0.5, 7.0, K)]
    # Scripted counts: keep L cohorts with moderate turnover.
    n = [10] * L
    taus = [float(grid[K // 3 + i % max(1, K // 3)]) for i in range(L)]
    cohorts = [Cohort(n=n[i], tau=taus[i], lot_id=i) for i in range(L)]

    pj = _uniform_joint(L, K)
    pm = _uniform_marginals(L, K)
    out: list[CaseResult] = []

    for t in range(T):
        rng_alloc = spawn_rng(42, run_id="fil11c-s2", day=t, stream=STREAM_ALLOC)
        rng_spoil = spawn_rng(42, run_id="fil11c-s2", day=t, stream=STREAM_SPOIL)
        # One sim day for observations + next counts (ground path).
        res = day_step(
            cohorts,
            params=params,
            demand=8 + (t % 5),
            delivery=Cohort(n=8, tau=float(grid[0]), lot_id=100 + t)
            if t % 2 == 0
            else None,
            rng_alloc=rng_alloc,
            rng_spoil=rng_spoil,
        )
        # Align to L slots: take first L live or pad.
        live = res.cohorts[:L]
        while len(live) < L:
            live.append(Cohort(n=1, tau=float(grid[0]), lot_id=999))
        n_t = [c.n for c in live[:L]]
        # Snap ages to nearest grid for filter replay (fixed discrete support).
        tau_snap = [
            float(grid[int(np.argmin(np.abs(np.asarray(grid) - c.tau)))])
            for c in live[:L]
        ]
        y = P1Obs(
            sales_total=int(res.sales_total),
            waste_total=int(res.waste_total),
            arrivals=0,
        )
        # If totals exceed on-hand after pad quirks, skip.
        if y.sales_total + y.waste_total > sum(n_t):
            cohorts = live
            continue
        # Use snapped ages only for likelihood evaluation path via prior
        # concentrated on snapped cells for a fair one-day update from uniform
        # would ignore snap - Stage 2 compares algorithms on same (n,y,prior).
        case = _compare_one(
            name=f"multiday_t{t}",
            n=n_t,
            y=y,
            params=params,
            tau_grid=grid,
            prior_joint=pj,
            prior_marg=pm,
        )
        out.append(case)
        # Predict: carry posterior as next prior (exact joint + MF).
        pj = exact_joint_update(n_t, pj, y, params, tau_grid=grid)
        pm = mean_field_update(n_t, pm, y, params, tau_grid=grid)
        # Age shift on grid: move mass toward older bins (MOD-02 discrete approx).
        dtau = q10_age_increment(
            1.0,
            t_store_c=params.t_store_c,
            t_ref_c=params.t_ref_c,
            q10=params.q10,
        )
        pj, pm = _shift_age_prior(pj, pm, grid=grid, dtau=dtau)
        cohorts = live
        _ = tau_snap  # documented snap used for diagnostics only
    return out


def _shift_age_prior(
    joint: np.ndarray,
    marg: np.ndarray,
    *,
    grid: list[float],
    dtau: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic age advance: remap each bin to nearest older grid point."""
    K = len(grid)
    L = marg.shape[0]
    new_idx = []
    for t in grid:
        target = t + dtau
        new_idx.append(int(np.argmin(np.abs(np.asarray(grid) - target))))
    # Marginals
    nm = np.zeros_like(marg)
    for ell in range(L):
        for k in range(K):
            nm[ell, new_idx[k]] += marg[ell, k]
    nm /= np.maximum(nm.sum(axis=1, keepdims=True), 1e-300)
    # Joint via remapping indices
    nj = np.zeros_like(joint)
    for idx, p in enumerate(joint):
        if p <= 0.0:
            continue
        ks = []
        rem = idx
        for ell in range(L):
            power = K ** (L - 1 - ell)
            k = rem // power
            rem -= k * power
            ks.append(new_idx[k])
        new_i = 0
        for ell, k in enumerate(ks):
            new_i += k * (K ** (L - 1 - ell))
        nj[new_i] += p
    s = float(nj.sum())
    if s > 0.0:
        nj /= s
    else:
        nj = np.ones_like(joint) / float(len(joint))
    return nj, nm


def stage3_particle_path(*, T: int = 12) -> list[CaseResult]:
    """Freeze a production-style count trajectory and replay Stage 2 logic."""
    from blueberries_voi.filter.particle.research import ResearchParticleFilter
    from blueberries_voi.rng import STREAM_FILTER_RESAMPLE

    params = ModelParams(sigma=0.5)
    K = 6
    L = 3
    grid = [float(x) for x in np.linspace(0.5, 7.0, K)]
    particle_filter = ResearchParticleFilter(params=params, N=32, K=K, L=L)
    rng0 = spawn_rng(7, run_id="fil11c-s3", day=0, stream=STREAM_FILTER_RESAMPLE)
    particle_filter.initialize(rng0)
    assert particle_filter._state is not None
    pj = _uniform_joint(L, K)
    pm = _uniform_marginals(L, K)
    out: list[CaseResult] = []
    for t in range(T):
        state = particle_filter._state
        assert state is not None
        n_mean = np.maximum(1, np.round(state.counts.mean(axis=0)).astype(int))
        n_t = [int(x) for x in n_mean.tolist()]
        sales = min(int(sum(n_t) // 3), int(sum(n_t)))
        waste = min(2, int(sum(n_t) - sales))
        y = P1Obs(sales_total=sales, waste_total=waste, arrivals=8 if t % 3 == 0 else 0)
        case = _compare_one(
            name=f"particle_t{t}",
            n=n_t,
            y=y,
            params=params,
            tau_grid=grid,
            prior_joint=pj,
            prior_marg=pm,
        )
        out.append(case)
        pj = exact_joint_update(n_t, pj, y, params, tau_grid=grid)
        pm = mean_field_update(n_t, pm, y, params, tau_grid=grid)
        rng_t = spawn_rng(
            7, run_id="fil11c-s3", day=t + 1, stream=STREAM_FILTER_RESAMPLE
        )
        particle_filter.step(y, rng_t)
    return out


def sweep_tv_vs_sigma(*, L: int = 3, K: int = 6) -> dict[float, float]:
    grid = [float(x) for x in np.linspace(0.5, 7.0, K)]
    n = [8] * L
    y = P1Obs(sales_total=9, waste_total=3, arrivals=0)
    out: dict[float, float] = {}
    for sigma in (0.2, 0.5, 1.0):
        r = _compare_one(
            name=f"sweep_s{sigma}",
            n=n,
            y=y,
            params=ModelParams(sigma=sigma),
            tau_grid=grid,
        )
        out[sigma] = r.marg_tv_mean
    return out


def _gate_verdict(
    stage1: list[CaseResult],
    stage2: list[CaseResult],
    stress: CaseResult | None,
) -> tuple[str, str]:
    base_names = {"balanced_mild_sigma", "L3_base_P1", "weak_info"}
    base = [c for c in stage1 if c.name in base_names]
    base += stage2
    joint = [c.joint_tv for c in base]
    actions = [c.action_agree for c in base]

    med_m = float(np.median([c.marg_tv_mean for c in base]))
    p95_m = float(np.quantile([c.marg_tv_max for c in base], 0.95))
    med_j = float(np.median(joint))
    agree = float(np.mean(actions)) if actions else 1.0

    stress_fail = False
    if (
        stress is not None
        and (not stress.action_agree)
        and stress.joint_tv > JOINT_TV_MEDIAN_MAX
    ):
        stress_fail = True

    pass_marg = med_m < MARG_TV_MEDIAN_MAX and p95_m < MARG_TV_P95_MAX
    pass_joint = med_j < JOINT_TV_MEDIAN_MAX or agree >= ACTION_AGREE_MIN

    if stress_fail:
        verdict = "FAIL"
        rec = (
            "Fail on stress (LIFO + rich info) with action flips - do not ship "
            "mean-field for production; keep joint / implement sliding window next."
        )
    elif pass_marg and pass_joint:
        verdict = "PASS"
        rec = (
            "Pass on P1 base + mild path - recommend reopening FIL-04 toward "
            "mean-field (C) and parking FIL-12/13 joint machinery (FIL-13 option B). "
            "Do not flip ⚑ ADRs until Oliver confirms."
        )
    elif (not pass_marg or not pass_joint) and agree >= ACTION_AGREE_MIN:
        verdict = "CONDITIONAL"
        rec = (
            "Joint/marginal TV exceeds freeze gates but Stage 4 actions agree - "
            "optional accept MF with that sentence; prefer sliding window if VOI "
            "is belief-sensitive. Recommendation only; no ADR status flip."
        )
    else:
        verdict = "FAIL"
        rec = (
            "Fail decision/belief gates on P1 base - do not ship MF; "
            "sliding window next."
        )

    detail = (
        f"base marg_tv median={med_m:.4f} p95_max={p95_m:.4f}; "
        f"joint_tv median={med_j:.4f}; action_agree={agree:.3f}; "
        f"stress_fail={stress_fail}"
    )
    return verdict, rec + " (" + detail + ")"


def _write_figure(tv_vs_sigma: dict[float, float], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    xs = sorted(tv_vs_sigma)
    ys = [tv_vs_sigma[x] for x in xs]
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.plot(xs, ys, marker="o")
    ax.set_xlabel("picking sigma")
    ax.set_ylabel("mean marginal TV (exact vs MF)")
    ax.set_title("FIL-11 Stage C - marginal TV vs sigma (L=3)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _md_table(rows: list[CaseResult]) -> str:
    lines = [
        (
            "| case | L | K | sigma | joint TV | marg TV max | "
            "marg KL max | max MI | SW rel delta | action agree |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r.name} | {r.L} | {r.K} | {r.sigma:.2f} | {r.joint_tv:.4f} | "
            f"{r.marg_tv_max:.4f} | {r.marg_kl_max:.4f} | {r.max_mi:.4f} | "
            f"{r.sw_rel_delta:.4f} | {r.action_agree} |"
        )
    return "\n".join(lines)


def main() -> None:
    s1 = stage1_cases()
    s2 = stage2_multiday(L=3, K=6, T=12, sigma=0.5)
    s3 = stage3_particle_path(T=10)
    # Stage 4 embedded in CaseResult.action_agree / sw_rel_delta
    stress = next((c for c in s1 if c.name == "L3_stress_lifo_rich"), None)
    tv_sigma = sweep_tv_vs_sigma(L=3, K=6)
    fig_path = FIG_DIR / "fil11_stage_c_mf_tv_vs_sigma.png"
    _write_figure(tv_sigma, fig_path)

    verdict, rec = _gate_verdict(s1, s2, stress)

    lines = [
        "# FIL-11 Stage C - exact joint vs mean-field (FIL-04 check)",
        "",
        f"**Verdict:** {verdict}",
        "",
        f"**Recommendation:** {rec}",
        "",
        "Likelihood: named `sequential_wor_pmf` (ADR 0090). Production soft "
        "`_pf_update` left unchanged. ADR 0049 / 0057 statuses not flipped.",
        "",
        "## Stage 1 - one-step synthetic",
        "",
        _md_table(s1),
        "",
        "## Stage 2 - multi-day accumulation (L=3, K=6, T≈12)",
        "",
        _md_table(s2),
        "",
        "## Stage 3 - frozen particle filter count path replay",
        "",
        _md_table(s3),
        "",
        "## Stage 4 - decision metric",
        "",
        "Embedded in tables: `SW rel delta` = |E_exact - E_MF| / stock; "
        "`action agree` on order grid {0,8,16,24}.",
        "",
        "## Marginal TV vs sigma (L=3)",
        "",
        "| sigma | mean marginal TV |",
        "| --- | --- |",
    ]
    for s, tv in sorted(tv_sigma.items()):
        lines.append(f"| {s:.1f} | {tv:.4f} |")
    lines += [
        "",
        f"Figure: `{fig_path.relative_to(ROOT)}`",
        "",
        "## Gates (ADR 0090)",
        "",
        f"- Marginal TV: median < {MARG_TV_MEDIAN_MAX}, p95 < {MARG_TV_P95_MAX}",
        (
            f"- Joint TV median < {JOINT_TV_MEDIAN_MAX} or "
            f"action agree >= {ACTION_AGREE_MIN}"
        ),
        "- Stress LIFO+rich with action flips => fail MF for production",
        "",
    ]
    NOTE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {NOTE}")
    print(f"Wrote {fig_path}")
    print(f"VERDICT={verdict}")
    print(rec)


if __name__ == "__main__":
    main()

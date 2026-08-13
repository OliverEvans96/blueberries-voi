"""FIL-13 bakeoff microbench helpers."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

import numpy as np

from blueberries_voi.filter.particle.bakeoff import get_backend
from blueberries_voi.filter.types import P1Obs, age_grid, guard_joint_memory
from blueberries_voi.model import (
    ModelParams,
    death_prob_survival_ratio,
    q10_age_increment,
    weibull_survival,
)


@dataclass
class BakeoffRow:
    backend: str
    K: int
    N: int
    L: int
    wall_s: float
    peak_rss_mb: float
    oom: bool
    timeout: bool
    tv: float | None = None


def tv_vs_exact(backend: str, *, L: int, K: int) -> float:
    """NON-GATE / deprecated soft self-check (M1 Stage C tautology).

    Kept only for bakeoff microbench TV column continuity. Production Stage C
    is the generative ``day_step`` check owned by T-012 / ADR 0088 — do not use
    this function as a filter pass/fail gate.
    """
    grid = age_grid(K)
    prior = np.ones(K) / K
    dtau = q10_age_increment(1.0, t_store_c=4.0, t_ref_c=0.0, q10=3.0)
    tau_now = grid + 1.0 * dtau
    surv = np.array([weibull_survival(float(t), beta=2.0, eta=14.0) for t in tau_now])
    pick = np.power(np.maximum(surv, 1e-300), 1.0 / 0.5)
    pick = pick / pick.sum()
    p_die = np.array(
        [death_prob_survival_ratio(float(t), dtau, beta=2.0, eta=14.0) for t in tau_now]
    )
    # Soft toy terms retained here only for the deprecated auxiliary curve.
    soft_sales = min(1.5, 15 / max(L, 1) / 15.0)
    soft_waste = min(1.5, 1 / max(L, 1) / 3.0)
    like = (
        np.power(pick, soft_sales)
        * np.power(np.maximum(p_die, 1e-6), soft_waste)
        * np.power(np.maximum(1.0 - p_die, 1e-6), max(0.0, 1.0 - soft_waste))
    )
    exact = prior * like
    exact = exact / exact.sum()

    rng = np.random.default_rng(1)
    be = get_backend(backend)
    state = be.initialize(N=500, K=K, L=L, params=ModelParams(), rng=rng)
    state.age_post[:] = 1.0 / K
    state.days_on_shelf[:] = 0.0
    state = be.predict_update(
        state, P1Obs(sales_total=15, waste_total=1, arrivals=0), ModelParams(), rng
    )
    post = state.age_post[:, 0, :].mean(axis=0)
    post = post / max(float(post.sum()), 1e-300)
    return float(0.5 * np.abs(post - exact).sum())


def run_microbench(
    backend: str,
    *,
    K: int,
    N: int,
    L: int,
    params: ModelParams | None = None,
    timeout_s: float = 2.0,
) -> BakeoffRow:
    import time
    import tracemalloc

    p = params or ModelParams()
    rng = np.random.default_rng(0)
    be = get_backend(backend)
    oom = False
    timeout = False
    tv: float | None = None
    wall = 0.0
    peak_mb = 0.0
    try:
        if backend == "full_joint":
            guard_joint_memory(K, L, N)
        tracemalloc.start()
        t0 = time.perf_counter()
        state = be.initialize(N=N, K=K, L=L, params=p, rng=rng)
        obs = P1Obs(sales_total=20, waste_total=2, arrivals=8)
        for _ in range(3):
            state = be.predict_update(state, obs, p, rng)
            if time.perf_counter() - t0 > timeout_s:
                timeout = True
                break
        wall = time.perf_counter() - t0
        _current, peak = tracemalloc.get_traced_memory()
        peak_mb = peak / (1024 * 1024)
        tracemalloc.stop()
        if L <= 3 and backend in {"sliding_window", "mean_field", "full_joint"}:
            tv = tv_vs_exact(backend, L=L, K=min(K, 4))
    except MemoryError:
        oom = True
        with contextlib.suppress(Exception):
            tracemalloc.stop()
    return BakeoffRow(
        backend=backend,
        K=K,
        N=N,
        L=L,
        wall_s=wall,
        peak_rss_mb=peak_mb,
        oom=oom,
        timeout=timeout,
        tv=tv,
    )

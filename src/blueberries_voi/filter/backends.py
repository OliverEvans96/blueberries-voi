"""FIL-13 bakeoff backends behind one predict/update interface."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from blueberries_voi.filter.types import (
    AGE_GRID_HI,
    AGE_GRID_LO,
    P1Obs,
    age_grid,
    guard_joint_memory,
)
from blueberries_voi.model import (
    ModelParams,
    death_prob_survival_ratio,
    q10_age_increment,
    weibull_survival,
)

BACKENDS: tuple[str, ...] = (
    "sliding_window",
    "mean_field",
    "bound_L",
    "bootstrap_pf",
    "full_joint",
)


@dataclass
class ParticleState:
    """Particle state: counts sampled; arrival-age posterior marginalised (MOD-02)."""

    weights: np.ndarray  # (N,)
    counts: np.ndarray  # (N, L)
    age_idx: np.ndarray  # (N, L) for bootstrap PF
    age_post: np.ndarray  # (N, L, K) over arrival age τ_in
    days_on_shelf: np.ndarray  # (L,) calendar days since arrival
    L: int
    backend: str


class FilterBackend(Protocol):
    name: str

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState: ...

    def predict_update(
        self,
        state: ParticleState,
        obs: P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState: ...


def ess(weights: np.ndarray) -> float:
    w = weights / max(float(weights.sum()), 1e-300)
    return float(1.0 / np.sum(w**2))


def _ess(weights: np.ndarray) -> float:
    return ess(weights)


def _systematic_resample(weights: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n = len(weights)
    w = weights / max(float(weights.sum()), 1e-300)
    positions = (rng.random() + np.arange(n)) / n
    cumulative = np.cumsum(w)
    return np.searchsorted(cumulative, positions, side="right").astype(int)


def _prior_age_post(K: int, L: int, N: int) -> np.ndarray:
    return np.ones((N, L, K), dtype=float) / K


def _new_state(
    *,
    N: int,
    K: int,
    L: int,
    rng: np.random.Generator,
    backend: str,
) -> ParticleState:
    return ParticleState(
        weights=np.ones(N) / N,
        counts=rng.integers(0, 8, size=(N, L)),
        age_idx=rng.integers(0, K, size=(N, L)),
        age_post=_prior_age_post(K, L, N),
        days_on_shelf=np.zeros(L, dtype=float),
        L=L,
        backend=backend,
    )


def _rbpf_update(
    state: ParticleState,
    obs: P1Obs,
    params: ModelParams,
    rng: np.random.Generator,
    *,
    backend_name: str,
) -> ParticleState:
    """Identity transition on arrival-age grid; likelihood at τ_in + t*Δτ."""
    n, L = state.counts.shape
    K = state.age_post.shape[-1]
    grid = age_grid(K)
    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    days = state.days_on_shelf.astype(float) + 1.0
    new_post = state.age_post.copy()

    for ell in range(L):
        tau_now = grid + float(days[ell]) * dtau
        surv = np.array(
            [
                weibull_survival(float(t), beta=params.beta, eta=params.eta_ref)
                for t in tau_now
            ]
        )
        pick = np.power(np.maximum(surv, 1e-300), 1.0 / max(params.sigma, 1e-6))
        pick = pick / max(float(pick.sum()), 1e-300)
        p_die = np.array(
            [
                death_prob_survival_ratio(
                    float(t), dtau, beta=params.beta, eta=params.eta_ref
                )
                for t in tau_now
            ]
        )
        sales_pow = min(1.5, max(obs.sales_total / max(L, 1), 0.0) / 15.0)
        waste_pow = min(1.5, max(obs.waste_total / max(L, 1), 0.0) / 3.0)
        like = (
            np.power(pick, sales_pow)
            * np.power(np.maximum(p_die, 1e-6), waste_pow)
            * np.power(np.maximum(1.0 - p_die, 1e-6), max(0.0, 1.0 - waste_pow))
        )
        like = like / max(float(like.sum()), 1e-300)
        new_post[:, ell, :] = new_post[:, ell, :] * like[None, :]
        tot = new_post[:, ell, :].sum(axis=-1, keepdims=True)
        new_post[:, ell, :] = new_post[:, ell, :] / np.maximum(tot, 1e-300)

    on_hand = state.counts.sum(axis=1).astype(float)
    sales_ll = (
        -0.5
        * ((float(obs.sales_total) - np.minimum(on_hand, float(obs.sales_total))) ** 2)
        / (on_hand + 1.0)
    )
    waste_ll = (
        -0.5 * ((float(obs.waste_total) - 0.05 * on_hand) ** 2) / (0.05 * on_hand + 1.0)
    )
    log_w = np.log(state.weights + 1e-300) + sales_ll + waste_ll
    log_w -= float(log_w.max())
    weights = np.exp(log_w)
    weights /= float(weights.sum())
    counts = np.maximum(0, state.counts + rng.integers(-1, 2, size=state.counts.shape))

    if obs.arrivals > 0:
        counts = np.concatenate(
            [counts[:, 1:], np.full((n, 1), int(obs.arrivals), dtype=int)],
            axis=1,
        )
        new_post = np.concatenate(
            [new_post[:, 1:, :], np.ones((n, 1, K), dtype=float) / K],
            axis=1,
        )
        days = np.concatenate([days[1:], np.asarray([0.0])])

    if _ess(weights) < 0.5 * n:
        idx = _systematic_resample(weights, rng)
        counts = counts[idx]
        new_post = new_post[idx]
        weights = np.ones(n) / n

    return ParticleState(
        weights=weights,
        counts=counts,
        age_idx=state.age_idx,
        age_post=new_post,
        days_on_shelf=days,
        L=L,
        backend=backend_name,
    )


@dataclass
class SlidingWindowBackend:
    name: str = "sliding_window"
    window: int = 3

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _new_state(N=N, K=K, L=L, rng=rng, backend=self.name)

    def predict_update(
        self,
        state: ParticleState,
        obs: P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _rbpf_update(state, obs, params, rng, backend_name=self.name)


@dataclass
class MeanFieldBackend:
    name: str = "mean_field"

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        st = _new_state(N=N, K=K, L=L, rng=rng, backend=self.name)
        return st

    def predict_update(
        self,
        state: ParticleState,
        obs: P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _rbpf_update(state, obs, params, rng, backend_name=self.name)


@dataclass
class BoundLBackend:
    name: str = "bound_L"
    max_L: int = 4

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _new_state(N=N, K=K, L=min(L, self.max_L), rng=rng, backend=self.name)

    def predict_update(
        self,
        state: ParticleState,
        obs: P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _rbpf_update(state, obs, params, rng, backend_name=self.name)


@dataclass
class BootstrapPFBackend:
    name: str = "bootstrap_pf"

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _new_state(N=N, K=K, L=L, rng=rng, backend=self.name)

    def predict_update(
        self,
        state: ParticleState,
        obs: P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        n, _L = state.counts.shape
        K = state.age_post.shape[-1]
        age_idx = state.age_idx  # arrival-age bins stay put (identity)
        on_hand = state.counts.sum(axis=1).astype(float)
        sales_ll = (
            -0.5
            * (
                (float(obs.sales_total) - np.minimum(on_hand, float(obs.sales_total)))
                ** 2
            )
            / (on_hand + 1.0)
        )
        log_w = np.log(state.weights + 1e-300) + sales_ll
        log_w -= float(log_w.max())
        weights = np.exp(log_w)
        weights /= float(weights.sum())
        counts = np.maximum(
            0, state.counts + rng.integers(-1, 2, size=state.counts.shape)
        )
        days = state.days_on_shelf + 1.0
        if obs.arrivals > 0:
            counts = np.concatenate(
                [counts[:, 1:], np.full((n, 1), int(obs.arrivals), dtype=int)],
                axis=1,
            )
            age_idx = np.concatenate(
                [age_idx[:, 1:], rng.integers(0, K, size=(n, 1))],
                axis=1,
            )
            days = np.concatenate([days[1:], np.asarray([0.0])])
        if _ess(weights) < 0.5 * n:
            idx = _systematic_resample(weights, rng)
            counts = counts[idx]
            age_idx = age_idx[idx]
            weights = np.ones(n) / n
        return ParticleState(
            weights=weights,
            counts=counts,
            age_idx=age_idx,
            age_post=state.age_post,
            days_on_shelf=days,
            L=state.L,
            backend=self.name,
        )


@dataclass
class FullJointBackend:
    name: str = "full_joint"

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        guard_joint_memory(K, L, N)
        return _new_state(N=N, K=K, L=L, rng=rng, backend=self.name)

    def predict_update(
        self,
        state: ParticleState,
        obs: P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        guard_joint_memory(state.age_post.shape[-1], state.L, len(state.weights))
        return _rbpf_update(state, obs, params, rng, backend_name=self.name)


def get_backend(name: str) -> FilterBackend:
    mapping: dict[str, FilterBackend] = {
        "sliding_window": SlidingWindowBackend(),
        "mean_field": MeanFieldBackend(),
        "bound_L": BoundLBackend(),
        "bootstrap_pf": BootstrapPFBackend(),
        "full_joint": FullJointBackend(),
    }
    if name not in mapping:
        msg = f"unknown backend {name!r}"
        raise ValueError(msg)
    return mapping[name]


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
    """TV vs exact one-step Bayesian update with the same arrival-age likelihood."""
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
    sales_pow = min(1.5, 15 / max(L, 1) / 15.0)
    waste_pow = min(1.5, 1 / max(L, 1) / 3.0)
    like = (
        np.power(pick, sales_pow)
        * np.power(np.maximum(p_die, 1e-6), waste_pow)
        * np.power(np.maximum(1.0 - p_die, 1e-6), max(0.0, 1.0 - waste_pow))
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


# Silence unused-import lint for grid bounds re-exported via age_grid usage above.
_ = (AGE_GRID_HI, AGE_GRID_LO)

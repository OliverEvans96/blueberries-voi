"""Diagnostic exact-joint / mean-field updates and joint↔marginal metrics."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.filter.types import P1Obs, age_grid

from .exact_likelihood import log_p_sales_waste_given_ages

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

    from blueberries_voi.model import ModelParams

# Shared production mean-field sweep budget (ADR 0104 / T-044).
MF_MAX_SWEEPS = 5
_MF_TV_STOP = 1e-6


def _infer_k(prior_joint: NDArray[np.floating], L: int) -> int:
    n_cells = int(prior_joint.shape[0])
    if L <= 0:
        msg = "L must be positive"
        raise ValueError(msg)
    k_f = n_cells ** (1.0 / float(L))
    k: int = round(k_f)
    if k**L != n_cells:
        msg = f"prior_joint length {n_cells} is not K^{L} for integer K"
        raise ValueError(msg)
    return k


def _decode_ages(idx: int, *, L: int, K: int, tau_grid: Sequence[float]) -> list[float]:
    """Lot 0 is most significant digit in base-K."""
    ages: list[float] = []
    rem = idx
    for ell in range(L):
        power = K ** (L - 1 - ell)
        k = rem // power
        rem -= k * power
        ages.append(float(tau_grid[k]))
    return ages


def _decode_indices(idx: int, *, L: int, K: int) -> tuple[int, ...]:
    rem = idx
    out: list[int] = []
    for ell in range(L):
        power = K ** (L - 1 - ell)
        k = rem // power
        rem -= k * power
        out.append(int(k))
    return tuple(out)


def _resolve_tau_grid(
    *,
    K: int,
    tau_grid: Sequence[float] | NDArray[np.floating] | None,
) -> list[float]:
    if tau_grid is None:
        return [float(x) for x in age_grid(K)]
    grid = [float(x) for x in tau_grid]
    if len(grid) != K:
        msg = f"tau_grid length {len(grid)} != K={K}"
        raise ValueError(msg)
    return grid


def exact_joint_update(
    n: Sequence[int] | NDArray[np.integer],
    prior_joint: NDArray[np.floating],
    y: P1Obs,
    params: ModelParams,
    *,
    tau_grid: Sequence[float] | NDArray[np.floating] | None = None,
) -> NDArray[np.floating]:
    """Exact Bayes update over flat ``K^L`` joint (lot 0 = MS digit)."""
    n_l = [int(x) for x in n]
    L = len(n_l)
    prior = np.asarray(prior_joint, dtype=float).reshape(-1)
    K = _infer_k(prior, L)
    grid = _resolve_tau_grid(K=K, tau_grid=tau_grid)

    log_post = np.full(K**L, -np.inf, dtype=float)
    for idx in range(K**L):
        p0 = float(prior[idx])
        if p0 <= 0.0:
            continue
        tau = _decode_ages(idx, L=L, K=K, tau_grid=grid)
        ll = log_p_sales_waste_given_ages(
            n_l, tau, y.sales_total, y.waste_total, params
        )
        if math.isfinite(ll):
            log_post[idx] = math.log(p0) + ll

    m = float(np.max(log_post))
    if not math.isfinite(m):
        return np.ones(K**L, dtype=float) / float(K**L)
    w = np.exp(log_post - m)
    w /= float(w.sum())
    return w


def _marginal_tv(a: NDArray[np.floating], b: NDArray[np.floating]) -> float:
    return 0.5 * float(np.abs(np.asarray(a) - np.asarray(b)).sum())


def mean_field_update(
    n: Sequence[int] | NDArray[np.integer],
    prior_marginals: NDArray[np.floating],
    y: P1Obs,
    params: ModelParams,
    *,
    tau_grid: Sequence[float] | NDArray[np.floating] | None = None,
    max_sweeps: int = MF_MAX_SWEEPS,
    tv_stop: float = _MF_TV_STOP,
) -> NDArray[np.floating]:
    """Coordinate-ascent mean-field with mean age plug-ins (≤ ``max_sweeps``)."""
    n_l = [int(x) for x in n]
    L = len(n_l)
    q = np.asarray(prior_marginals, dtype=float).copy()
    if q.ndim != 2 or q.shape[0] != L:
        msg = f"prior_marginals must have shape (L, K); got {q.shape}"
        raise ValueError(msg)
    K = int(q.shape[1])
    grid = np.asarray(_resolve_tau_grid(K=K, tau_grid=tau_grid), dtype=float)
    prior = q.copy()
    # Normalize rows.
    q = q / np.maximum(q.sum(axis=1, keepdims=True), 1e-300)

    for _ in range(max_sweeps):
        q_old = q.copy()
        for ell in range(L):
            mean_tau = [
                float(np.dot(q[j], grid)) if j != ell else 0.0 for j in range(L)
            ]
            log_unnorm = np.full(K, -np.inf, dtype=float)
            for k in range(K):
                p0 = float(prior[ell, k])
                if p0 <= 0.0:
                    continue
                tau = list(mean_tau)
                tau[ell] = float(grid[k])
                ll = log_p_sales_waste_given_ages(
                    n_l, tau, y.sales_total, y.waste_total, params
                )
                if math.isfinite(ll):
                    log_unnorm[k] = math.log(p0) + ll
            m = float(np.max(log_unnorm))
            if not math.isfinite(m):
                q[ell, :] = 1.0 / float(K)
            else:
                w = np.exp(log_unnorm - m)
                q[ell, :] = w / float(w.sum())
        max_change = max(_marginal_tv(q[ell], q_old[ell]) for ell in range(L))
        if max_change < tv_stop:
            break
    return np.asarray(q, dtype=float)


def induced_joint_from_marginals(
    marginals: NDArray[np.floating],
) -> NDArray[np.floating]:
    """Product joint product  q_l with lot-0 most-significant flat indexing."""
    q = np.asarray(marginals, dtype=float)
    L, K = q.shape
    joint = np.ones(K**L, dtype=float)
    for idx in range(K**L):
        ks = _decode_indices(idx, L=L, K=K)
        p = 1.0
        for ell, k in enumerate(ks):
            p *= float(q[ell, k])
        joint[idx] = p
    s = float(joint.sum())
    if s <= 0.0:
        return np.ones(K**L, dtype=float) / float(K**L)
    return joint / s


def joint_total_variation(p: NDArray[np.floating], q: NDArray[np.floating]) -> float:
    return 0.5 * float(np.abs(np.asarray(p) - np.asarray(q)).sum())


def marginals_from_joint(
    joint: NDArray[np.floating], *, L: int, K: int
) -> NDArray[np.floating]:
    j = np.asarray(joint, dtype=float).reshape(-1)
    marg = np.zeros((L, K), dtype=float)
    for idx in range(K**L):
        ks = _decode_indices(idx, L=L, K=K)
        p = float(j[idx])
        for ell, k in enumerate(ks):
            marg[ell, k] += p
    marg /= np.maximum(marg.sum(axis=1, keepdims=True), 1e-300)
    return marg


def marginal_total_variation(p: NDArray[np.floating], q: NDArray[np.floating]) -> float:
    return _marginal_tv(p, q)


def marginal_kl(p: NDArray[np.floating], q: NDArray[np.floating]) -> float:
    """KL(p || q) for one simplex row."""
    pp = np.asarray(p, dtype=float)
    qq = np.asarray(q, dtype=float)
    mask = pp > 0.0
    return float(np.sum(pp[mask] * np.log(pp[mask] / np.maximum(qq[mask], 1e-300))))


def joint_kl(p: NDArray[np.floating], q: NDArray[np.floating]) -> float:
    pp = np.asarray(p, dtype=float).reshape(-1)
    qq = np.asarray(q, dtype=float).reshape(-1)
    mask = pp > 0.0
    return float(np.sum(pp[mask] * np.log(pp[mask] / np.maximum(qq[mask], 1e-300))))


def max_pairwise_mutual_information(
    joint: NDArray[np.floating], *, L: int, K: int
) -> float:
    """Max pairwise MI under the exact joint (nats)."""
    if L < 2:
        return 0.0
    j = np.asarray(joint, dtype=float).reshape(-1)
    marg = marginals_from_joint(j, L=L, K=K)
    best = 0.0
    for a in range(L):
        for b in range(a + 1, L):
            # Pair joint p(k_a, k_b)
            pair = np.zeros((K, K), dtype=float)
            for idx in range(K**L):
                ks = _decode_indices(idx, L=L, K=K)
                pair[ks[a], ks[b]] += float(j[idx])
            mi = 0.0
            for i in range(K):
                for jj in range(K):
                    p_ab = float(pair[i, jj])
                    if p_ab <= 0.0:
                        continue
                    p_a = float(marg[a, i])
                    p_b = float(marg[b, jj])
                    mi += p_ab * math.log(p_ab / max(p_a * p_b, 1e-300))
            best = max(best, mi)
    return float(best)

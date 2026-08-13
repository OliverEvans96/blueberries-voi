"""FIL-11 Stage C / FIL-04 evidence: ``sequential_wor_pmf`` joint vs mean-field.

Shared filter density matching ``allocate_sales`` (sequential WOR product) plus
independent Binomial waste via ``death_prob_survival_ratio``. Production particle
weights stay on MC ``observation_loglik_mc`` (ADR 0087); age belief under P1 uses
``mean_field_update`` on the mean_field backend (ADR 0091 / T-021).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.filter.types import P1Obs, age_grid
from blueberries_voi.model import (
    ModelParams,
    death_prob_survival_ratio,
    picking_weights,
    q10_age_increment,
    weibull_survival,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

# Re-exported for import-identity AC (T-020).
__all__ = [
    "MF_MAX_SWEEPS",
    "death_prob_survival_ratio",
    "exact_joint_update",
    "induced_joint_from_marginals",
    "joint_kl",
    "joint_total_variation",
    "log_p_sales_waste_given_ages",
    "marginal_kl",
    "marginal_total_variation",
    "max_pairwise_mutual_information",
    "mean_field_update",
    "picking_weights",
    "survival_weighted_on_hand",
]

# Shared production mean-field sweep budget (ADR 0104 / T-044).
MF_MAX_SWEEPS = 5
_MF_TV_STOP = 1e-6


def _binom_pmf(k: int, n: int, p: float) -> float:
    if k < 0 or k > n or n < 0:
        return 0.0
    p_c = min(1.0, max(0.0, float(p)))
    return float(math.comb(n, k) * (p_c**k) * ((1.0 - p_c) ** (n - k)))


def sequential_wor_composition_probs(
    counts: Sequence[int],
    sales_tot: int,
    weights: NDArray[np.floating],
) -> dict[tuple[int, ...], float]:
    """PMF over sales compositions under the ``allocate_sales`` pick loop (DP).

    Among nonempty cohorts, pick proportional to fixed ``weights`` (not
    ``remaining * weights``) - matching ``model.allocate_sales``.
    """
    counts_l = [int(c) for c in counts]
    L = len(counts_l)
    if L == 0:
        return {(): 1.0} if sales_tot == 0 else {}
    if sales_tot < 0 or sales_tot > int(sum(counts_l)):
        return {}
    if sales_tot == 0:
        return {tuple(0 for _ in range(L)): 1.0}

    # Flat index for composition c: mix-radix with digit bounds (n_i+1).
    dims = [c + 1 for c in counts_l]
    size = 1
    for d in dims:
        size *= d
    strides = [1] * L
    for i in range(L - 2, -1, -1):
        strides[i] = strides[i + 1] * dims[i + 1]

    def pack(c: Sequence[int]) -> int:
        return sum(int(c[i]) * strides[i] for i in range(L))

    def unpack(idx: int) -> tuple[int, ...]:
        out: list[int] = []
        rem = idx
        for i in range(L):
            out.append(rem // strides[i])
            rem %= strides[i]
        return tuple(out)

    cur = np.zeros(size, dtype=float)
    cur[pack([0] * L)] = 1.0
    w = np.asarray(weights, dtype=float)

    for _ in range(sales_tot):
        nxt = np.zeros(size, dtype=float)
        for idx, p in enumerate(cur):
            if p <= 0.0:
                continue
            c = unpack(idx)
            avail = [float(w[j]) if c[j] < counts_l[j] else 0.0 for j in range(L)]
            tot = float(sum(avail))
            if tot <= 0.0:
                continue
            for j in range(L):
                if avail[j] <= 0.0:
                    continue
                c2 = list(c)
                c2[j] += 1
                nxt[pack(c2)] += p * (avail[j] / tot)
        cur = nxt

    out: dict[tuple[int, ...], float] = {}
    for idx, p in enumerate(cur):
        if p > 0.0:
            out[unpack(idx)] = float(p)
    return out


def sequential_wor_composition_prob(
    counts: Sequence[int],
    sales: Sequence[int],
    weights: NDArray[np.floating],
) -> float:
    """PMF of one sales composition under ``allocate_sales`` (via DP table)."""
    sales_l = [int(s) for s in sales]
    demand = int(sum(sales_l))
    table = sequential_wor_composition_probs(counts, demand, weights)
    return float(table.get(tuple(sales_l), 0.0))


def _iter_compositions(totals: Sequence[int], target: int) -> list[tuple[int, ...]]:
    """Nonnegative integer compositions c with sum(c)==target and c_i <= totals_i."""
    totals_t = tuple(int(t) for t in totals)
    L = len(totals_t)
    out: list[tuple[int, ...]] = []

    def rec(i: int, left: int, acc: list[int]) -> None:
        if i == L - 1:
            if 0 <= left <= totals_t[i]:
                out.append(tuple([*acc, left]))
            return
        for v in range(0, min(totals_t[i], left) + 1):
            acc.append(v)
            rec(i + 1, left - v, acc)
            acc.pop()

    if target < 0:
        return out
    rec(0, target, [])
    return out


def log_p_sales_waste_given_ages(
    n: Sequence[int] | NDArray[np.integer],
    tau: Sequence[float] | NDArray[np.floating],
    sales_tot: int,
    waste_tot: int,
    params: ModelParams,
) -> float:
    """Log P1 likelihood: ``sequential_wor_pmf`` sales x Binomial waste.

    Marginalizes latent per-lot sales/waste compositions consistent with totals.
    If ``sales_tot < sum(n)`` then demand ``D = sales_tot``; else stockout
    (sold the whole shelf, composition fixed to ``n``).
    """
    n_l = [int(x) for x in n]
    tau_l = [float(t) for t in tau]
    if len(n_l) != len(tau_l):
        msg = "n and tau must have the same length"
        raise ValueError(msg)
    on_hand = int(sum(n_l))
    if sales_tot < 0 or waste_tot < 0 or sales_tot > on_hand:
        return float("-inf")
    max_waste = on_hand - sales_tot
    if waste_tot > max_waste:
        return float("-inf")

    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    w = picking_weights(
        tau_l,
        sigma=params.sigma,
        beta=params.beta,
        eta=params.eta_ref,
        uniform=params.uniform_picking,
    )
    p_die = [
        death_prob_survival_ratio(t, dtau, beta=params.beta, eta=params.eta_ref)
        for t in tau_l
    ]

    if sales_tot == on_hand:
        sales_probs_map: dict[tuple[int, ...], float] = {tuple(n_l): 1.0}
    else:
        sales_probs_map = sequential_wor_composition_probs(n_l, sales_tot, w)

    like = 0.0
    for sales, p_sales in sales_probs_map.items():
        if p_sales <= 0.0:
            continue
        remaining = [n_i - s_i for n_i, s_i in zip(n_l, sales, strict=True)]
        p_waste = 0.0
        for waste in _iter_compositions(remaining, waste_tot):
            term = 1.0
            for w_i, r_i, p_i in zip(waste, remaining, p_die, strict=True):
                term *= _binom_pmf(int(w_i), int(r_i), float(p_i))
            p_waste += term
        like += p_sales * p_waste

    if like <= 0.0:
        return float("-inf")
    return float(math.log(like))


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


def survival_weighted_on_hand(
    n: Sequence[int | float],
    joint_or_marginals: NDArray[np.floating],
    *,
    params: ModelParams,
    tau_grid: Sequence[float],
    from_marginals: bool = False,
) -> float:
    """sum  n_l E[S(tau_l)] under joint or product marginals.

    ``n`` may be integer lot sizes or fractional expected counts (MF means);
    values are kept continuous (not floored).
    """
    n_l = [float(x) for x in n]
    L = len(n_l)
    grid = [float(t) for t in tau_grid]
    K = len(grid)
    if from_marginals:
        marg = np.asarray(joint_or_marginals, dtype=float)
    else:
        marg = marginals_from_joint(
            np.asarray(joint_or_marginals, dtype=float), L=L, K=K
        )
    total = 0.0
    for ell in range(L):
        e_s = 0.0
        for k in range(K):
            s = weibull_survival(grid[k], beta=params.beta, eta=params.eta_ref)
            e_s += float(marg[ell, k]) * s
        total += float(n_l[ell]) * e_s
    return float(total)

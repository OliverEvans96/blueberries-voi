"""Exact sequential-WOR and multinomial sales/waste log-likelihoods."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from blueberries_voi.model import (
    ModelParams,
    death_prob_survival_ratio,
    picking_weights,
    q10_age_increment,
)

from .sequential_wor import sequential_wor_composition_probs

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy as np
    from numpy.typing import NDArray


def _binom_pmf(k: int, n: int, p: float) -> float:
    if k < 0 or k > n or n < 0:
        return 0.0
    p_c = min(1.0, max(0.0, float(p)))
    return float(math.comb(n, k) * (p_c**k) * ((1.0 - p_c) ** (n - k)))


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


def _multinomial_pmf(counts: Sequence[int], n: int, probs: Sequence[float]) -> float:
    """Multinomial PMF for a composition with ``sum(counts)==n``."""
    if n < 0 or int(sum(counts)) != n:
        return 0.0
    p = [float(x) for x in probs]
    if any(x < 0.0 for x in p):
        return 0.0
    total_p = float(sum(p))
    if total_p <= 0.0:
        return 0.0
    p = [x / total_p for x in p]
    # n! / (c0! c1! …) * ∏ p_i^{c_i}
    coef = math.factorial(n)
    term = 1.0
    for c_i, p_i in zip(counts, p, strict=True):
        c = int(c_i)
        if c < 0:
            return 0.0
        coef //= math.factorial(c)
        if c > 0 and p_i <= 0.0:
            return 0.0
        term *= p_i**c
    return float(coef) * term


def log_p_sales_waste_multinomial_given_ages(
    n: Sequence[int] | NDArray[np.integer],
    tau: Sequence[float] | NDArray[np.floating],
    sales_tot: int,
    waste_tot: int,
    params: ModelParams,
) -> float:
    """Ablation log-likelihood: multinomial sales x Binomial waste.

    Not the production default (ADR 0105); select via
    ``sales_likelihood="multinomial"``. Enumerates inventory-feasible
    compositions and scores sales with a with-replacement multinomial on
    picking weights, then independent Binomial waste on remainders.
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

    w_l = [float(x) for x in w]
    like = 0.0
    for sales in _iter_compositions(n_l, sales_tot):
        p_sales = _multinomial_pmf(sales, sales_tot, w_l)
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

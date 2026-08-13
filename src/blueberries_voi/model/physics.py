"""Constitutive physics and demand kernels (Weibull, Q10, picking, NB)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from blueberries_voi.model.params import ModelParams


def weibull_survival(tau: float, *, beta: float, eta: float) -> float:
    """Weibull survival S(τ) = exp(-(τ/η)^β); S(0)=1."""
    if tau <= 0.0:
        return 1.0
    if eta <= 0.0:
        msg = "eta must be positive"
        raise ValueError(msg)
    return float(np.exp(-((tau / eta) ** beta)))


def death_prob_survival_ratio(
    tau: float,
    dtau: float,
    *,
    beta: float,
    eta: float,
) -> float:
    """One-step death probability via survival ratio (never hazardxdt)."""
    if dtau <= 0.0:
        return 0.0
    s0 = weibull_survival(tau, beta=beta, eta=eta)
    if s0 <= 0.0:
        return 1.0
    s1 = weibull_survival(tau + dtau, beta=beta, eta=eta)
    return float(1.0 - s1 / s0)


def death_prob_hazard_product(
    tau: float,
    dtau: float,
    *,
    beta: float,
    eta: float,
) -> float:
    """First-order hazardxdt approximation (for regression contrast only)."""
    if dtau <= 0.0 or tau < 0.0:
        return 0.0
    # h(τ) = (β/η) (τ/η)^{β-1}
    if tau == 0.0:
        if beta > 1.0:
            return 0.0
        if beta < 1.0:
            return 1.0
        return float(min(1.0, (1.0 / eta) * dtau))
    hazard = (beta / eta) * ((tau / eta) ** (beta - 1.0))
    return float(min(1.0, max(0.0, hazard * dtau)))


def q10_age_increment(
    dt_calendar: float,
    *,
    t_store_c: float,
    t_ref_c: float,
    q10: float,
) -> float:
    """Effective-age advance over a calendar interval under constant T."""
    factor = q10 ** ((t_store_c - t_ref_c) / 10.0)
    return float(dt_calendar * factor)


def picking_weights(
    taus: Sequence[float],
    *,
    sigma: float,
    beta: float,
    eta: float,
    uniform: bool = False,
) -> np.ndarray:
    """Survival-power picking weights w ∝ S(τ)^(1/sigma); uniform when requested."""
    n = len(taus)
    if n == 0:
        return np.zeros(0, dtype=float)
    if uniform or sigma <= 0.0:
        return np.full(n, 1.0 / n, dtype=float)
    surv = np.array(
        [weibull_survival(float(t), beta=beta, eta=eta) for t in taus],
        dtype=float,
    )
    raw = np.power(np.maximum(surv, 1e-300), 1.0 / sigma)
    total = float(raw.sum())
    if total <= 0.0:
        return np.full(n, 1.0 / n, dtype=float)
    return cast("np.ndarray", raw / total)


def allocate_sales(
    counts: Sequence[int],
    demand: int,
    weights: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sequential without-replacement allocation (Wallenius simulation)."""
    n_cohorts = len(counts)
    sales = np.zeros(n_cohorts, dtype=int)
    remaining = np.array(counts, dtype=int)
    on_hand = int(remaining.sum())
    to_sell = min(int(demand), on_hand)
    w = np.asarray(weights, dtype=float).copy()
    if w.shape != (n_cohorts,):
        msg = "weights must match cohort count"
        raise ValueError(msg)
    for _ in range(to_sell):
        mask = remaining > 0
        if not np.any(mask):
            break
        avail_w = np.where(mask, w, 0.0)
        total = float(avail_w.sum())
        if total <= 0.0:
            # Fall back to uniform over nonempty cohorts.
            avail_w = mask.astype(float)
            total = float(avail_w.sum())
        probs = avail_w / total
        idx = int(rng.choice(n_cohorts, p=probs))
        sales[idx] += 1
        remaining[idx] -= 1
    return sales


def draw_demand(
    rng: np.random.Generator,
    params: ModelParams,
    *,
    day: int | None = None,
) -> int:
    """Negative binomial demand; optional calendar μ(day) via demand_profile."""
    mu = params.demand_mu_for_day(day)
    if params.demand_vm <= 1.0:
        msg = "demand_vm must be > 1 for overdispersed NB"
        raise ValueError(msg)
    r = mu / (params.demand_vm - 1.0)
    p = r / (r + mu)
    return int(rng.negative_binomial(r, p))


__all__ = [
    "allocate_sales",
    "death_prob_hazard_product",
    "death_prob_survival_ratio",
    "draw_demand",
    "picking_weights",
    "q10_age_increment",
    "weibull_survival",
]

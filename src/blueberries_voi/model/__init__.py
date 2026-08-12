"""Shared model kernels (MOD-12 day_step and constitutive physics)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from blueberries_voi.rng import STREAM_ALLOC, STREAM_DEMAND, STREAM_SPOIL

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class ModelParams:
    """Interim M1 constitutive and demand defaults."""

    beta: float = 2.0
    eta_ref: float = 14.0  # days at T_ref
    q10: float = 3.0
    t_ref_c: float = 0.0
    t_store_c: float = 4.0
    sigma: float = 0.5
    demand_mu: float = 30.0
    demand_vm: float = 2.0  # V/M => NB r = mu / (vm - 1)
    case_size: int = 8
    uniform_picking: bool = False

    def nb_r(self) -> float:
        """Negative-binomial dispersion ``r`` (scipy ``n``) from mean and V/M."""
        if self.demand_vm <= 1.0:
            msg = "demand_vm must be > 1 for overdispersed NB"
            raise ValueError(msg)
        return self.demand_mu / (self.demand_vm - 1.0)

    def nb_p(self) -> float:
        """Scipy nbinom success probability: mean = r * (1-p) / p."""
        r = self.nb_r()
        return r / (r + self.demand_mu)


@dataclass
class Cohort:
    """One live inventory lot (count + effective age)."""

    n: int
    tau: float
    lot_id: int = 0


@dataclass
class DayStepResult:
    """Outputs of one shared MOD-12 day transition."""

    cohorts: list[Cohort]
    demand: int
    sales_total: int
    sales_by_cohort: np.ndarray
    waste_total: int
    waste_by_cohort: np.ndarray
    order_of_ops: tuple[str, ...] = field(
        default=("age", "demand", "allocate", "spoil", "deliver")
    )


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


def draw_demand(rng: np.random.Generator, params: ModelParams) -> int:
    """Negative binomial demand under MOD-26 defaults (scipy nbinom)."""
    r = params.nb_r()
    p = params.nb_p()
    return int(rng.negative_binomial(r, p))


def day_step(
    cohorts: Sequence[Cohort],
    *,
    params: ModelParams,
    demand: int | None = None,
    delivery: Cohort | None = None,
    rng_demand: np.random.Generator | None = None,
    rng_alloc: np.random.Generator | None = None,
    rng_spoil: np.random.Generator | None = None,
    event_log: list[str] | None = None,
) -> DayStepResult:
    """Apply MOD-12 events: age → demand → allocate → spoil → deliver."""
    live = [Cohort(n=c.n, tau=c.tau, lot_id=c.lot_id) for c in cohorts if c.n > 0]

    # 1. Age
    if event_log is not None:
        event_log.append("age")
    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    for c in live:
        c.tau += dtau

    # 2. Demand
    if event_log is not None:
        event_log.append("demand")
    if demand is None:
        if rng_demand is None:
            msg = "demand or rng_demand required"
            raise ValueError(msg)
        demand_draw = draw_demand(rng_demand, params)
    else:
        demand_draw = int(demand)

    # 3. Allocate sales
    if event_log is not None:
        event_log.append("allocate")
    if live:
        taus = [c.tau for c in live]
        counts = [c.n for c in live]
        weights = picking_weights(
            taus,
            sigma=params.sigma,
            beta=params.beta,
            eta=params.eta_ref,
            uniform=params.uniform_picking,
        )
        if rng_alloc is None:
            msg = "rng_alloc required when cohorts are live"
            raise ValueError(msg)
        sales_by = allocate_sales(counts, demand_draw, weights, rng_alloc)
        for i, c in enumerate(live):
            c.n -= int(sales_by[i])
    else:
        sales_by = np.zeros(0, dtype=int)
    sales_total = int(sales_by.sum())

    # 4. Spoil survivors
    if event_log is not None:
        event_log.append("spoil")
    waste_by = np.zeros(len(live), dtype=int)
    if live:
        if rng_spoil is None:
            msg = "rng_spoil required when cohorts are live"
            raise ValueError(msg)
        for i, c in enumerate(live):
            if c.n <= 0:
                continue
            p_die = death_prob_survival_ratio(
                c.tau,
                dtau,
                beta=params.beta,
                eta=params.eta_ref,
            )
            waste = int(rng_spoil.binomial(c.n, p_die))
            waste_by[i] = waste
            c.n -= waste
    waste_total = int(waste_by.sum())

    # Drop extinct cohorts (FIL-14=A: n==0 only).
    live = [c for c in live if c.n > 0]

    # 5. Deliver
    if event_log is not None:
        event_log.append("deliver")
    if delivery is not None and delivery.n > 0:
        live.append(Cohort(n=delivery.n, tau=delivery.tau, lot_id=delivery.lot_id))

    return DayStepResult(
        cohorts=live,
        demand=demand_draw,
        sales_total=sales_total,
        sales_by_cohort=sales_by,
        waste_total=waste_total,
        waste_by_cohort=waste_by,
    )


# Re-export stream names used by callers wiring day_step RNGs.
__all__ = [
    "STREAM_ALLOC",
    "STREAM_DEMAND",
    "STREAM_SPOIL",
    "Cohort",
    "DayStepResult",
    "ModelParams",
    "allocate_sales",
    "day_step",
    "death_prob_hazard_product",
    "death_prob_survival_ratio",
    "draw_demand",
    "picking_weights",
    "q10_age_increment",
    "weibull_survival",
]


def _shared_day_step_symbol() -> Any:
    """Identity used by shared-import gate tests."""
    return day_step

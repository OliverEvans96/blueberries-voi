"""Damped survival-weighted base-stock policy (CTL-01=C / ADR 0058).

Protection interval under daily delivery LT=1 (X-11 / ADR 0006) used R=1 plus
L=1 → demand over R+L=2 calendar days. Under CAL-01 MWF cadence (CAL-A3 /
T-081 / ADR 0112), protection length is **day-indexed** via
``OrderSchedule.protection_days(day)`` (3 / 3 / 4 on Sun / Tue / Thu).

With a calendar demand profile (CAL-B4 / T-132 / ADR 0134), the protection
quantile sums heterogeneous daily NB demands μ(day+k) via Monte Carlo; without
a profile the closed-form homogeneous ``NB(n·r, p)`` path is unchanged.

The lead-time age increment ``delta_tau_L`` remains the LT=1 scalar shared
with Rung 0: ``q10_age_increment(1.0, ...)`` under store temperatures.

Order quantity (Nahmias rho damping; default rho=0.8):

    q_t = case_round(rho * [F^{-1}_{D_{t:t+L}}(alpha) - I_tilde_t]^+)

where ``I_tilde_t`` is f-native ``effective_inventory`` on ``ShelfBelief`` and
``F^{-1}`` is the alpha-quantile of protection-window demand for calendar days
``day .. day+n-1``. Non-order days return 0 when an ``OrderSchedule`` is attached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueberries_voi.filter.belief import ShelfBelief, effective_inventory
from blueberries_voi.model import ModelParams, q10_age_increment
from blueberries_voi.model.demand_fractile import protection_interval_quantile
from blueberries_voi.sim.bakeoff_ordering import case_round

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from blueberries_voi.sim.order_schedule import OrderSchedule

LEAD_TIME_DAYS: int = 1
PROTECTION_DEMAND_DAYS: int = 2  # R+L under daily LT=1 (legacy / no schedule)


def protection_demand_quantile(
    alpha: float,
    params: ModelParams,
    *,
    protection_days: int,
    start_day: int = 0,
    n_mc: int = 20_000,
    mc_seed: int | None = None,
) -> float:
    """Alpha-quantile of protection-window NB demand.

    Homogeneous μ when no profile; heterogeneous MC when ``demand_profile`` is set
    (ADR 0134). ``start_day`` is the calendar day of the first demand day in the
    window (typically the order day).
    """
    return protection_interval_quantile(
        alpha,
        params,
        protection_days=protection_days,
        start_day=start_day,
        n_mc=n_mc,
        mc_seed=mc_seed,
    )


def _protection_demand_quantile(
    alpha: float,
    params: ModelParams,
    *,
    protection_days: int = PROTECTION_DEMAND_DAYS,
    start_day: int = 0,
) -> float:
    """Alpha-quantile of protection-interval demand."""
    return protection_demand_quantile(
        alpha,
        params,
        protection_days=protection_days,
        start_day=start_day,
    )


class DampedSurvivalWeightedPolicy:
    """CTL-01 damped SW base-stock: caseRound(rho[F^{-1}(alpha) - I_tilde]^+).

    Consumes ``ShelfBelief`` only (ADR 0092). Default rho=0.8; alpha is required
    (tuned later by T-029). With ``schedule`` / ``protection_days`` callable,
    protection length is day-indexed (CAL-A3); otherwise legacy scalar 2.
    """

    LEAD_TIME_DAYS: int = LEAD_TIME_DAYS
    PROTECTION_DEMAND_DAYS: int = PROTECTION_DEMAND_DAYS

    def __init__(
        self,
        *,
        rho: float = 0.8,
        alpha: float,
        params: ModelParams,
        schedule: OrderSchedule | None = None,
        protection_days: int | Callable[[int], int] | None = None,
    ) -> None:
        self.rho = float(rho)
        self.alpha = float(alpha)
        self.params = params
        self.f_pipeline_default = 1.0
        self.schedule = schedule
        self._protection_days = protection_days
        self.lead_time = LEAD_TIME_DAYS
        # Legacy attribute: scalar default; day-indexed path resolves per order.
        self.protection_demand_days = (
            int(protection_days)
            if isinstance(protection_days, int)
            else PROTECTION_DEMAND_DAYS
        )
        self.delta_tau_L = float(
            q10_age_increment(
                float(LEAD_TIME_DAYS),
                t_store_c=params.t_store_c,
                t_ref_c=params.t_ref_c,
                q10=params.q10,
            )
        )

    def _resolve_protection_days(self, day: int) -> int:
        if callable(self._protection_days):
            return int(self._protection_days(day))
        if isinstance(self._protection_days, int):
            return int(self._protection_days)
        if self.schedule is not None:
            return int(self.schedule.protection_days(day))
        return PROTECTION_DEMAND_DAYS

    def order(
        self,
        belief: ShelfBelief,
        *,
        day: int = 0,
        pending_orders: Mapping[int, int] | None = None,
        schedule: OrderSchedule | None = None,
    ) -> int:
        """Return case-rounded damped SW order for the given shelf belief."""
        sched = schedule if schedule is not None else self.schedule
        if sched is not None and not sched.can_order(day):
            return 0
        pending: Mapping[int, int] = {} if pending_orders is None else pending_orders
        i_tilde = float(
            effective_inventory(
                belief,
                pending_orders=pending,
                f_pipeline_default=self.f_pipeline_default,
            )
        )
        # Prefer call-site schedule for can_order; protection length follows
        # injected callable / int, else schedule.protection_days(day), else 2.
        if callable(self._protection_days) or isinstance(self._protection_days, int):
            n_days = self._resolve_protection_days(day)
        elif sched is not None:
            n_days = int(sched.protection_days(day))
        else:
            n_days = self._resolve_protection_days(day)
        d_star = _protection_demand_quantile(
            self.alpha,
            self.params,
            protection_days=n_days,
            start_day=day,
        )
        raw = self.rho * max(0.0, d_star - i_tilde)
        return int(case_round(raw, self.params.case_size))


__all__ = [
    "LEAD_TIME_DAYS",
    "PROTECTION_DEMAND_DAYS",
    "DampedSurvivalWeightedPolicy",
    "protection_demand_quantile",
]

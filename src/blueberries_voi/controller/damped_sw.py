"""Damped survival-weighted base-stock policy (CTL-01=C / ADR 0058).

Protection interval (daily delivery LT=1, X-11 / ADR 0006): review horizon R=1
plus lead time L=1 -> demand over R+L=2 calendar days. The lead-time age
increment ``delta_tau_L`` is the same scalar Rung 0 (CTL-06) will share:
``q10_age_increment(1.0, ...)`` under store temperatures.

Order quantity (Nahmias rho damping; default rho=0.8):

    q_t = case_round(rho * [F^{-1}_{D_{t:t+L}}(alpha) - I_tilde_t]^+)

where ``I_tilde_t`` is T-023 ``effective_inventory`` on ``ShelfBelief`` (MF
marginals) and ``F^{-1}`` is the alpha-quantile of the sum of two i.i.d. daily
NB demands (``NB(2*nb_r, nb_p)`` under ``ModelParams`` / scipy ``nbinom``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scipy.stats import nbinom

from blueberries_voi.controller.ordering import case_round
from blueberries_voi.filter.belief import ShelfBelief, effective_inventory
from blueberries_voi.model import ModelParams, q10_age_increment

if TYPE_CHECKING:
    from collections.abc import Mapping

LEAD_TIME_DAYS: int = 1
PROTECTION_DEMAND_DAYS: int = 2  # R+L under daily LT=1


def _protection_demand_quantile(alpha: float, params: ModelParams) -> float:
    """Alpha-quantile of protection-interval demand (2 i.i.d. daily NB)."""
    if not 0.0 < alpha < 1.0:
        msg = f"alpha must be in (0, 1), got {alpha}"
        raise ValueError(msg)
    r = float(params.nb_r()) * float(PROTECTION_DEMAND_DAYS)
    p = float(params.nb_p())
    return float(nbinom.ppf(alpha, r, p))


class DampedSurvivalWeightedPolicy:
    """CTL-01 damped SW base-stock: caseRound(rho[F^{-1}(alpha) - I_tilde]^+).

    Consumes ``ShelfBelief`` only (ADR 0092). Default rho=0.8; alpha is required
    (tuned later by T-029). Lead time LT=1 and ``delta_tau_L`` match the Rung 0
    daily-delivery convention.
    """

    LEAD_TIME_DAYS: int = LEAD_TIME_DAYS
    PROTECTION_DEMAND_DAYS: int = PROTECTION_DEMAND_DAYS

    def __init__(
        self,
        *,
        rho: float = 0.8,
        alpha: float,
        params: ModelParams,
    ) -> None:
        self.rho = float(rho)
        self.alpha = float(alpha)
        self.params = params
        self.lead_time = LEAD_TIME_DAYS
        self.protection_demand_days = PROTECTION_DEMAND_DAYS
        self.delta_tau_L = float(
            q10_age_increment(
                float(LEAD_TIME_DAYS),
                t_store_c=params.t_store_c,
                t_ref_c=params.t_ref_c,
                q10=params.q10,
            )
        )

    def order(
        self,
        belief: ShelfBelief,
        *,
        day: int = 0,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int:
        """Return case-rounded damped SW order for the given shelf belief."""
        del day  # deterministic in belief/pending; day reserved for episode API
        pending: Mapping[int, int] = {} if pending_orders is None else pending_orders
        i_tilde = float(
            effective_inventory(belief, pending_orders=pending, params=self.params)
        )
        d_star = _protection_demand_quantile(self.alpha, self.params)
        raw = self.rho * max(0.0, d_star - i_tilde)
        return int(case_round(raw, self.params.case_size))


__all__ = [
    "LEAD_TIME_DAYS",
    "PROTECTION_DEMAND_DAYS",
    "DampedSurvivalWeightedPolicy",
]

"""Shared NB protection-interval demand quantile (homogeneous μ)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from scipy.stats import nbinom

if TYPE_CHECKING:
    from blueberries_voi.model import ModelParams


def protection_demand_quantile(
    alpha: float,
    params: ModelParams,
    *,
    protection_days: int,
) -> float:
    """Alpha-quantile of ``protection_days`` i.i.d. daily NB demand.

    Homogeneous μ: scale NB ``r`` by ``protection_days`` (ADR 0116 / T-081).
    Call sites pass their own length / alpha; this helper does not unify
    schedule-aware vs legacy scalar conventions.
    """
    if not 0.0 < float(alpha) < 1.0:
        msg = f"alpha must be in (0, 1), got {alpha}"
        raise ValueError(msg)
    r = float(params.nb_r()) * float(protection_days)
    p = float(params.nb_p())
    return float(nbinom.ppf(float(alpha), r, p))


__all__ = ["protection_demand_quantile"]

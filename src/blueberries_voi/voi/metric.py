"""VOI-01 metric: percentage headline + absolute dollar support vs P0."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "VoIMetric",
    "voi_vs_p0",
]


@dataclass(frozen=True)
class VoIMetric:
    """VOI-01=C: absolute $ delta and percentage vs P0."""

    absolute_delta: float
    pct_vs_p0: float


def voi_vs_p0(profit_scenario: float, profit_p0: float) -> VoIMetric:
    """Return absolute_delta and pct_vs_p0 (scenario - P0).

    Raises ``ValueError`` when ``profit_p0`` is exactly zero (unstable %).
    """
    p0 = float(profit_p0)
    scen = float(profit_scenario)
    if p0 == 0.0:
        msg = "profit_p0 is zero; percentage VOI vs P0 is undefined"
        raise ValueError(msg)
    absolute_delta = scen - p0
    return VoIMetric(absolute_delta=absolute_delta, pct_vs_p0=absolute_delta / p0)

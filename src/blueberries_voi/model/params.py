"""Model parameter and cohort types (MOD-12)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np  # noqa: TC002  # dataclass get_type_hints

from blueberries_voi.model.demand_profile import DemandProfile  # noqa: TC001


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
    demand_profile: DemandProfile | None = None

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

    def demand_mu_for_day(self, day: int | None) -> float:
        """Resolve NB mean: profile μ(day) when configured, else ``demand_mu``."""
        if day is not None and self.demand_profile is not None:
            return float(self.demand_profile.mu(day))
        return float(self.demand_mu)


@dataclass
class Cohort:
    """One live inventory lot (count + cumulative thermal exposure, reference-days)."""

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


__all__ = [
    "Cohort",
    "DayStepResult",
    "ModelParams",
]

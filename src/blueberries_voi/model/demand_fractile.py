"""Protection-interval demand fractiles (CAL-B4 / ADR 0134)."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import numpy as np
from scipy.stats import nbinom

if TYPE_CHECKING:
    from blueberries_voi.model import ModelParams

PROTECTION_MC_BASE_SEED: int = 0xC41B_4B4D
PROTECTION_MC_DEFAULT_N: int = 20_000
_FLAT_MU_ATOL: float = 1e-9


def derive_protection_mc_seed(
    start_day: int,
    protection_days: int,
    alpha: float,
    mc_seed: int | None,
) -> int:
    """Deterministic planning seed (independent of episode CRN)."""
    if mc_seed is not None:
        return int(mc_seed) & 0xFFFF_FFFF
    alpha_bits = struct.unpack("!I", struct.pack("!f", float(alpha)))[0]
    mixed = (
        PROTECTION_MC_BASE_SEED
        ^ (int(start_day) * 1_314_542_391)
        ^ (int(protection_days) * 2_654_435_761)
        ^ alpha_bits
    )
    return int(mixed & 0xFFFF_FFFF)


def _window_mus(
    params: ModelParams, start_day: int, protection_days: int
) -> list[float]:
    return [
        float(params.demand_mu_for_day(start_day + k)) for k in range(protection_days)
    ]


def _homogeneous_closed_form(
    alpha: float, mu: float, demand_vm: float, protection_days: int
) -> float:
    if demand_vm <= 1.0:
        msg = "demand_vm must be > 1 for overdispersed NB"
        raise ValueError(msg)
    r_day = mu / (demand_vm - 1.0)
    r_sum = r_day * float(protection_days)
    p = r_day / (r_day + mu)
    return float(nbinom.ppf(float(alpha), r_sum, p))


def heterogeneous_nb_sum_quantile_mc(
    alpha: float,
    mus: list[float],
    demand_vm: float,
    *,
    n_mc: int = PROTECTION_MC_DEFAULT_N,
    mc_seed: int | None = None,
    start_day: int = 0,
    protection_days: int | None = None,
) -> float:
    """Empirical alpha-quantile of sum of heterogeneous daily NB demands."""
    if not mus:
        return 0.0
    if not 0.0 < float(alpha) < 1.0:
        msg = f"alpha must be in (0, 1), got {alpha}"
        raise ValueError(msg)
    if demand_vm <= 1.0:
        msg = "demand_vm must be > 1 for overdispersed NB"
        raise ValueError(msg)

    prot = int(protection_days if protection_days is not None else len(mus))
    seed = derive_protection_mc_seed(start_day, prot, alpha, mc_seed)
    rng = np.random.default_rng(seed)

    samples = np.zeros(int(n_mc), dtype=np.float64)
    for mu in mus:
        r = float(mu) / (demand_vm - 1.0)
        p = r / (r + float(mu))
        samples += rng.negative_binomial(r, p, size=int(n_mc))

    return float(np.quantile(samples, alpha, method="higher"))


def protection_interval_quantile(
    alpha: float,
    params: ModelParams,
    *,
    protection_days: int,
    start_day: int = 0,
    n_mc: int = PROTECTION_MC_DEFAULT_N,
    mc_seed: int | None = None,
) -> float:
    """Route homogeneous fast paths or heterogeneous MC."""
    if not 0.0 < float(alpha) < 1.0:
        msg = f"alpha must be in (0, 1), got {alpha}"
        raise ValueError(msg)
    if protection_days <= 0:
        return 0.0

    if params.demand_profile is None:
        return _homogeneous_closed_form(
            alpha, float(params.demand_mu), float(params.demand_vm), protection_days
        )

    mus = _window_mus(params, start_day, protection_days)
    mu_min = min(mus)
    mu_max = max(mus)
    if mu_max - mu_min <= _FLAT_MU_ATOL:
        return _homogeneous_closed_form(
            alpha, mu_min, float(params.demand_vm), protection_days
        )

    return heterogeneous_nb_sum_quantile_mc(
        alpha,
        mus,
        float(params.demand_vm),
        n_mc=n_mc,
        mc_seed=mc_seed,
        start_day=start_day,
        protection_days=protection_days,
    )


__all__ = [
    "PROTECTION_MC_BASE_SEED",
    "PROTECTION_MC_DEFAULT_N",
    "derive_protection_mc_seed",
    "heterogeneous_nb_sum_quantile_mc",
    "protection_interval_quantile",
]

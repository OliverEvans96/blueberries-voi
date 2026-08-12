"""Gate 0a/0b calculations (X-13)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from blueberries_voi.model import ModelParams, weibull_survival
from blueberries_voi.model.abdella import (
    ShipmentTrace,
    arrival_age_from_path,
    load_abdella_shipments,
    shipment_arrival_age,
)


@dataclass(frozen=True)
class Gate0aResult:
    arrival_ages: np.ndarray
    durations_d: np.ndarray
    var_total: float
    var_duration: float
    var_temperature: float
    duration_share: float
    temperature_share: float


@dataclass(frozen=True)
class Gate0bResult:
    case_size: int
    gap_units: float
    gap_cases: float
    swallowed_by_caseround: bool
    gap_units_case4: float
    gap_cases_case4: bool


def gate0a_variance_decomposition(
    shipments: list[ShipmentTrace],
    params: ModelParams | None = None,
) -> Gate0aResult:
    """Decompose Var(τ_arrival) into duration vs temperature contributions."""
    p = params or ModelParams()
    ages = np.asarray(
        [shipment_arrival_age(s, q10=p.q10, t_ref_c=p.t_ref_c) for s in shipments],
        dtype=float,
    )
    durations = np.asarray([s.duration_d for s in shipments], dtype=float)
    mean_dur = float(np.mean(durations))
    # Grand-mean temperature across all samples (duration-only paths).
    all_temps = np.concatenate([s.temps_c for s in shipments])
    t_bar = float(np.mean(all_temps))

    ages_dur = np.empty(len(shipments), dtype=float)
    ages_temp = np.empty(len(shipments), dtype=float)
    for i, s in enumerate(shipments):
        # Duration-only: actual duration at constant grand-mean T.
        times = np.asarray([0.0, s.duration_d], dtype=float)
        temps_const = np.asarray([t_bar, t_bar], dtype=float)
        ages_dur[i] = arrival_age_from_path(
            temps_const, times, q10=p.q10, t_ref_c=p.t_ref_c
        )
        # Temperature-only: resample path onto mean duration (time stretch).
        if s.duration_d <= 0:
            ages_temp[i] = 0.0
            continue
        scale = mean_dur / s.duration_d
        times_scaled = s.times_d * scale
        ages_temp[i] = arrival_age_from_path(
            s.temps_c, times_scaled, q10=p.q10, t_ref_c=p.t_ref_c
        )

    var_total = float(np.var(ages, ddof=1))
    var_duration = float(np.var(ages_dur, ddof=1))
    var_temperature = float(np.var(ages_temp, ddof=1))
    denom = var_duration + var_temperature
    if denom <= 0.0:
        dur_share = temp_share = 0.0
    else:
        dur_share = var_duration / denom
        temp_share = var_temperature / denom
    return Gate0aResult(
        arrival_ages=ages,
        durations_d=durations,
        var_total=var_total,
        var_duration=var_duration,
        var_temperature=var_temperature,
        duration_share=dur_share,
        temperature_share=temp_share,
    )


def _survival_weighted_target(ages: np.ndarray, params: ModelParams) -> float:
    """Crude age-aware base-stock proxy: S̄^{-1} scaled demand fractile stand-in."""
    surv = np.array(
        [weibull_survival(float(a), beta=params.beta, eta=params.eta_ref) for a in ages]
    )
    mean_s = float(np.mean(surv))
    # Target inventory proportional to 1/mean survival (higher when older mix).
    return params.demand_mu / max(mean_s, 1e-6)


def gate0b_caseround_sensitivity(
    arrival_ages: np.ndarray,
    params: ModelParams | None = None,
    *,
    case_size: int = 8,
) -> Gate0bResult:
    """Compare true-mix vs prior-mean age composition base-stock targets."""
    p = params or ModelParams()
    ages = np.asarray(arrival_ages, dtype=float)
    true_target = _survival_weighted_target(ages, p)
    prior_mean_age = float(np.mean(ages))
    prior_target = _survival_weighted_target(np.full_like(ages, prior_mean_age), p)
    gap = abs(true_target - prior_target)

    def swallowed(gap_units: float, cs: int) -> bool:
        # caseRound swallows gaps smaller than one case.
        return gap_units < float(cs)

    gap4 = gap  # same physical gap; swallow check at case size 4
    return Gate0bResult(
        case_size=case_size,
        gap_units=float(gap),
        gap_cases=float(gap) / float(case_size),
        swallowed_by_caseround=swallowed(gap, case_size),
        gap_units_case4=float(gap4),
        gap_cases_case4=swallowed(gap4, 4),
    )


def run_gate0(
    *,
    abdella_root: Path | None = None,
    figures_dir: Path | None = None,
) -> tuple[Gate0aResult, Gate0bResult]:
    """Compute Gate 0a/0b and write figures under ``figures/m1/``."""
    import matplotlib.pyplot as plt

    shipments = load_abdella_shipments(abdella_root)
    params = ModelParams()
    g0a = gate0a_variance_decomposition(shipments, params)
    g0b = gate0b_caseround_sensitivity(g0a.arrival_ages, params, case_size=8)

    out = figures_dir or (Path(__file__).resolve().parents[3] / "figures" / "m1")
    out.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.bar(
        ["duration", "temperature"],
        [g0a.var_duration, g0a.var_temperature],
        color=["#2a6f97", "#ca6702"],
    )
    ax.set_ylabel("Variance of arrival effective age")
    ax.set_title(
        f"Gate 0a - Var(τ)={g0a.var_total:.3f}; duration share={g0a.duration_share:.0%}"
    )
    fig.tight_layout()
    fig.savefig(out / "gate0_variance.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.bar(
        ["gap (units)", "one case (8)", "one case (4)"],
        [g0b.gap_units, 8.0, 4.0],
        color=["#264653", "#8ab17d", "#e9c46a"],
    )
    ax.set_ylabel("Units")
    swallow = "swallowed" if g0b.swallowed_by_caseround else "NOT swallowed"
    ax.set_title(f"Gate 0b - caseRound @8: {swallow} (gap={g0b.gap_units:.2f})")
    fig.tight_layout()
    fig.savefig(out / "gate0_caseround.png", dpi=120)
    plt.close(fig)

    return g0a, g0b

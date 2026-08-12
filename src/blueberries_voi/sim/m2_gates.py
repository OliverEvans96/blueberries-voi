"""ENG-04 M2 validation gates (β=1 degeneracy, CRN desync, DP certificate).

These are library helpers under ``sim/`` (outside ``controller/``). Named
pytest node ids in ``tests/test_m2_gates.py`` are the CI contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueberries_voi.controller.ordering import case_round
from blueberries_voi.controller.rollout import detect_crn_desync
from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
from blueberries_voi.controller.toy_dp import gap_vs_rollout, solve_toy_dp
from blueberries_voi.filter.belief import ShelfBelief
from blueberries_voi.model import ModelParams
from blueberries_voi.rng import STREAM_DEMAND, STREAM_SPOIL

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "GateResult",
    "assert_beta1_degeneracy",
    "assert_crn_desync",
    "assert_dp_certificate",
    "probe_crn_desync_crossed",
]

_FLAT_W: float = 0.75
_DEMAND_TARGET: float = 64.0
_RHO: float = 1.0
_CASE_SIZE: int = 8
_PROTECTION_DAYS: int = 2


@dataclass(frozen=True)
class GateResult:
    """Outcome of an ENG-04 M2 gate."""

    ok: bool
    status: str = "ok"
    gap: float | None = None
    gap_vs_rollout: float | None = None
    report: Mapping[str, float] | None = None


def _belief(*, lot_counts: list[float]) -> ShelfBelief:
    grid = [0.0, 1.0, 2.0, 3.0, 4.0]
    k = len(grid)
    counts = [float(x) for x in lot_counts]
    margs: list[list[float]] = []
    for _ in counts:
        row = [0.0] * k
        row[0] = 1.0
        margs.append(row)
    return ShelfBelief(lot_counts=counts, age_marginals=margs, tau_grid=grid)


def _flat_age_aware_order(
    *,
    lot_counts: list[float],
    pending: dict[int, int],
    flat_w: float = _FLAT_W,
    demand_target: float = _DEMAND_TARGET,
    rho: float = _RHO,
    case_size: int = _CASE_SIZE,
) -> int:
    """Age-aware base-stock when ``w`` is constant (β=1 / flat-w fixture)."""
    total = float(sum(float(x) for x in lot_counts))
    inv = float(flat_w) * total + sum(
        float(q) * float(flat_w) for q in pending.values()
    )
    raw = float(rho) * max(0.0, float(demand_target) - inv)
    return int(case_round(raw, case_size))


def assert_beta1_degeneracy() -> GateResult:
    """β=1 / constant-w degeneracy: age-aware and age-blind orders coincide.

    When survival weight ``w`` is flat (constant), corrected age-blind (Rung 0)
    and the age-aware survival-weighted base-stock on the same protection
    interval must return identical case-rounded orders (CTL-05 / ENG-04).
    """
    params = ModelParams(case_size=_CASE_SIZE)
    age_blind = CorrectedAgeBlindPolicy(
        alpha=0.9,
        params=params,
        rho=_RHO,
        mean_survival_weight=_FLAT_W,
        pipeline_weight=_FLAT_W,
        demand_target=_DEMAND_TARGET,
        protection_days=_PROTECTION_DAYS,
        case_size=_CASE_SIZE,
    )
    cases: tuple[tuple[list[float], dict[int, int]], ...] = (
        ([40.0], {}),
        ([10.0, 15.0, 15.0], {1: 16}),
        ([8.0, 8.0], {1: 8, 2: 8}),
        ([0.0], {}),
        ([96.0], {1: 24}),
        ([20.0, 20.0], {1: 16}),
    )
    for lots, pending in cases:
        belief = _belief(lot_counts=lots)
        q_blind = int(age_blind.order(0, belief, pending_orders=pending))
        q_aware = _flat_age_aware_order(lot_counts=lots, pending=pending)
        if q_blind != q_aware:
            return GateResult(
                ok=False,
                status="fail",
            )
    return GateResult(ok=True, status="ok")


def assert_crn_desync(
    *,
    crossed: bool = False,
    desync: bool = False,
    force_desync: bool = False,
    root_seed: int = 11,
    run_id: str = "m2-crn-gate",
    day: int = 0,
    n_draws: int = 32,
) -> GateResult:
    """M2 gate wrapping T-030 ``detect_crn_desync`` (CI red if broken)."""
    force = bool(crossed or desync or force_desync)
    stream_b = STREAM_SPOIL if force else STREAM_DEMAND
    result = detect_crn_desync(
        address_a={
            "root_seed": int(root_seed),
            "run_id": run_id,
            "day": int(day),
            "stream": STREAM_DEMAND,
        },
        address_b={
            "root_seed": int(root_seed),
            "run_id": run_id,
            "day": int(day),
            "stream": stream_b,
        },
        n_draws=int(n_draws),
    )
    ok = bool(result.ok)
    # When probing intentional desync, ok=True would mean the gate is broken.
    if force:
        return GateResult(ok=ok, status=str(result.status))
    return GateResult(ok=ok, status=str(result.status))


def probe_crn_desync_crossed() -> GateResult:
    """Crossed demand/spoil streams must not report ok."""
    return assert_crn_desync(crossed=True)


def assert_dp_certificate() -> GateResult:
    """M2 gate requiring T-031 DP-gap report (CI red if broken / missing)."""
    toy = solve_toy_dp()
    gap = float(gap_vs_rollout(toy))
    report = {"gap_vs_rollout": gap}
    return GateResult(
        ok=gap >= 0.0 and gap == gap,
        status="ok",
        gap=gap,
        gap_vs_rollout=gap,
        report=report,
    )

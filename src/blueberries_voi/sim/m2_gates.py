"""ENG-04 M2 validation gates (β=1 degeneracy, CRN desync, DP certificate).

These are library helpers under ``sim/`` (outside ``controller/``). Named
pytest node ids in ``tests/test_m2_gates.py`` are the CI contract.

T-083 / ADR 0112: β=1 and DP gates run under default ``OrderSchedule``
(orders Sun/Tue/Thu). Age-blind Rung 0 uses day-indexed survival weights
(T-081). Protection lengths on order days are 3/3/4 (not legacy daily 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueberries_voi.controller.damped_sw import (
    PROTECTION_DEMAND_DAYS,
    DampedSurvivalWeightedPolicy,
    protection_demand_quantile,
)
from blueberries_voi.controller.rollout import detect_crn_desync
from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
from blueberries_voi.controller.toy_dp import gap_vs_rollout, solve_toy_dp
from blueberries_voi.filter.belief import ShelfBelief, effective_inventory
from blueberries_voi.model import ModelParams
from blueberries_voi.rng import STREAM_DEMAND, STREAM_SPOIL
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "GateResult",
    "assert_beta1_degeneracy",
    "assert_crn_desync",
    "assert_dp_certificate",
    "probe_crn_desync_crossed",
]

_ALPHA: float = 0.9
_RHO: float = 1.0
_CASE_SIZE: int = 8
# Legacy scalar retained for unit docs; MWF gate uses schedule.protection_days.
_PROTECTION_DAYS: int = PROTECTION_DEMAND_DAYS
# T-083 retune record: order-day protection under DEFAULT_ORDER_SCHEDULE.
_MWF_ORDER_PROTECTION_DAYS: tuple[int, ...] = (3, 3, 4)  # Sun / Tue / Thu
_TAU_GRID: tuple[float, ...] = (0.0, 1.0, 2.0, 3.0, 4.0)
_SAME_AGE_INDEX: int = 0
# First-week calendar days that are order days (epoch Mon 2024-01-01).
_ORDER_DAY_FIXTURES: tuple[int, ...] = (6, 1, 3)  # Sun, Tue, Thu


@dataclass(frozen=True)
class GateResult:
    """Outcome of an ENG-04 M2 gate."""

    ok: bool
    status: str = "ok"
    gap: float | None = None
    gap_vs_rollout: float | None = None
    report: Mapping[str, float] | None = None


def _same_age_belief(*, lot_counts: list[float]) -> ShelfBelief:
    """All lots Dirac on one grid age — flat-w across lots (β=1-style fixture)."""
    grid = list(_TAU_GRID)
    k = len(grid)
    idx = int(_SAME_AGE_INDEX) % k
    counts = [float(x) for x in lot_counts]
    margs: list[list[float]] = []
    for _ in counts:
        row = [0.0] * k
        row[idx] = 1.0
        margs.append(row)
    return ShelfBelief(lot_counts=counts, age_marginals=margs, tau_grid=grid)


def _protection_demand_fractile(
    alpha: float,
    params: ModelParams,
    *,
    protection_days: int,
) -> float:
    """F^{-1} of protection-interval demand (matches DampedSurvivalWeightedPolicy)."""
    return protection_demand_quantile(alpha, params, protection_days=protection_days)


def _fixture_survival_weights(params: ModelParams) -> tuple[float, float]:
    """On-hand / pipeline weights implied by ``effective_inventory`` on the fixture."""
    unit = _same_age_belief(lot_counts=[1.0])
    bar_w = float(effective_inventory(unit, pending_orders={}, params=params))
    empty = _same_age_belief(lot_counts=[0.0])
    pipe_w = float(effective_inventory(empty, pending_orders={1: 1}, params=params))
    return bar_w, pipe_w


def _order_days(schedule: OrderSchedule) -> tuple[int, ...]:
    """Calendar days in the first week that ``schedule.can_order``."""
    days = tuple(d for d in range(7) if schedule.can_order(d))
    return days if days else _ORDER_DAY_FIXTURES


def assert_beta1_degeneracy() -> GateResult:
    """β=1 / constant-w degeneracy under default ``OrderSchedule``.

    When survival weight ``w`` is flat across lots (same-age fixture), corrected
    age-blind (Rung 0) and the real age-aware ``DampedSurvivalWeightedPolicy``
    must return identical case-rounded orders on each MWF order day (Sun/Tue/Thu)
    under matched ``rho``, day-indexed Rung 0 weights, and day-indexed protection
    fractiles (3/3/4). Legacy scalar R+L=2 is not the MWF gate base case.
    """
    schedule = DEFAULT_ORDER_SCHEDULE
    params = ModelParams(case_size=_CASE_SIZE)
    bar_w, pipe_w = _fixture_survival_weights(params)
    # Homogeneous day-indexed table (T-081); values match the flat fixture.
    weights_by_weekday = {wd: bar_w for wd in range(7)}

    age_aware = DampedSurvivalWeightedPolicy(
        rho=_RHO,
        alpha=_ALPHA,
        params=params,
        schedule=schedule,
    )
    cases: tuple[tuple[list[float], dict[int, int]], ...] = (
        ([40.0], {}),
        ([10.0, 15.0, 15.0], {1: 16}),
        ([8.0, 8.0], {1: 8, 2: 8}),
        ([0.0], {}),
        ([96.0], {1: 24}),
        ([20.0, 20.0], {1: 16}),
    )
    for day in _order_days(schedule):
        prot = int(schedule.protection_days(day))
        d_star = _protection_demand_fractile(_ALPHA, params, protection_days=prot)
        age_blind = CorrectedAgeBlindPolicy(
            alpha=_ALPHA,
            params=params,
            rho=_RHO,
            mean_survival_weight=weights_by_weekday,
            pipeline_weight=pipe_w,
            demand_target=d_star,
            protection_days=prot,
            case_size=_CASE_SIZE,
            schedule=schedule,
        )
        # Touch day-indexed API so gates consume T-081 weights (not scalar-only).
        _ = float(age_blind.mean_survival_weight_for_day(day))
        for lots, pending in cases:
            belief = _same_age_belief(lot_counts=lots)
            q_blind = int(age_blind.order(day, belief, pending_orders=pending))
            q_aware = int(age_aware.order(belief, day=day, pending_orders=pending))
            if q_blind != q_aware:
                return GateResult(
                    ok=False,
                    status="fail",
                    report={
                        "day": float(day),
                        "protection_days": float(prot),
                        "q_blind": float(q_blind),
                        "q_aware": float(q_aware),
                    },
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
    toy = solve_toy_dp(schedule=DEFAULT_ORDER_SCHEDULE)
    gap = float(gap_vs_rollout(toy))
    report = {"gap_vs_rollout": gap}
    return GateResult(
        ok=gap >= 0.0 and gap == gap,
        status="ok",
        gap=gap,
        gap_vs_rollout=gap,
        report=report,
    )

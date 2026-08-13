"""T-033 multi-scenario closed-loop + empirical L remeasure (outside ``controller/``).

Primary eval beliefs: **P1** (RBPF → ``shelf_belief_from_rbpf``), **B-state**
(oracle → ``shelf_belief_from_oracle``), and **Rung 0** (age-blind). Other M1.5
masks get interface smoke only. Empirical live-cohort **L** is remeasured under
SW+rollout and written under ``experiments/`` (never ``controller/``). Production
backend remains ``counts_only`` (ADR 0105); no silent joint / age-MF revert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from blueberries_voi.controller.damped_sw import (
    PROTECTION_DEMAND_DAYS,
    DampedSurvivalWeightedPolicy,
)
from blueberries_voi.controller.protection import protection_demand_quantile
from blueberries_voi.controller.protocol import invoke_order
from blueberries_voi.controller.rollout import RolloutPolicy
from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
from blueberries_voi.filter import PRODUCTION_BACKEND, RBPF
from blueberries_voi.filter.belief import (
    ShelfBelief,
    empty_shelf_belief,
    shelf_belief_from_cohorts_oracle,
    shelf_belief_from_rbpf,
)
from blueberries_voi.filter.types import P1Obs, mask_for
from blueberries_voi.model import Cohort, ModelParams, day_step
from blueberries_voi.rng import (
    STREAM_ALLOC,
    STREAM_ARRIVAL_SENSOR,
    STREAM_ARRIVAL_SHIP,
    STREAM_DEMAND,
    STREAM_FILTER_RESAMPLE,
    STREAM_SPOIL,
    spawn_rng,
)
from blueberries_voi.sim import DayLog, EpisodeLog, LotState, generate_arrival_age
from blueberries_voi.sim.episode import case_round
from blueberries_voi.sim.profit import DEFAULT_PROFIT_COSTS, ProfitCosts, episode_profit
from blueberries_voi.sim.shipments import default_shipments

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from blueberries_voi.model.abdella import ShipmentTrace

BeliefMode = Literal["P1", "B-state", "Rung 0"]

PRIMARY_SCENARIOS: tuple[str, ...] = ("P1", "B-state", "Rung 0")
OTHER_MASKS: tuple[str, ...] = ("P0", "F1", "F1s", "F2a", "F2")

# Production counts-only backend (ADR 0105); never silently select joint / age-MF.
MULTI_SCENARIO_PRODUCTION_BACKEND: str = "counts_only"
DEFAULT_MULTI_SCENARIO_REPORT_PATH: str = "experiments/m2_multi_scenario_result.md"

_EPISODE_CALENDAR_EPOCH: date = date(2024, 1, 1)
_DEFAULT_ALPHA: float = 0.9
_CI_N_BURN: int = 1
_CI_N_SCORE: int = 2
_CI_ROLLOUT_H: int = 2
_CI_N_ROLLOUT_PATHS: int = 1
_CI_FILTER_N: int = 32
_EMPTY_TAU_GRID: tuple[float, ...] = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0)

__all__ = [
    "DEFAULT_MULTI_SCENARIO_REPORT_PATH",
    "MULTI_SCENARIO_PRODUCTION_BACKEND",
    "OTHER_MASKS",
    "PRIMARY_SCENARIOS",
    "PRODUCTION_BACKEND",
    "MultiScenarioResult",
    "run_m2_multi_scenario",
    "smoke_other_masks",
]


@dataclass(frozen=True)
class MultiScenarioResult:
    """Closed-loop multi-scenario comparison under a shared root seed."""

    scenarios: tuple[str, ...]
    profits: Mapping[str, float]
    production_backend: str = MULTI_SCENARIO_PRODUCTION_BACKEND
    artifact_paths: tuple[Path, ...] = field(default_factory=tuple)
    empirical_l: Mapping[str, float] = field(default_factory=dict)
    root_seed: int = 0
    report_path: Path | None = None
    other_mask_smoke: Mapping[str, bool] | None = None


def smoke_other_masks(
    masks: Sequence[str] | None = None,
) -> dict[str, bool]:
    """Interface smoke for non-primary M1.5 masks (no full profit claims)."""
    names = list(masks) if masks is not None else list(OTHER_MASKS)
    out: dict[str, bool] = {}
    for name in names:
        # Construct ObsMask only — no closed-loop / profit evaluation.
        mask_for(name)
        out[str(name)] = True
    return out


def _protection_demand_fractile(alpha: float, params: ModelParams) -> float:
    """F^{-1} of protection-interval demand (matches alpha_tune / m2_gates / SW)."""
    return protection_demand_quantile(
        alpha, params, protection_days=PROTECTION_DEMAND_DAYS
    )


def _empty_shelf_belief() -> ShelfBelief:
    return empty_shelf_belief(tau_grid=_EMPTY_TAU_GRID)


def _oracle_belief(cohorts: Sequence[Cohort]) -> ShelfBelief:
    """B-state ShelfBelief via ``shelf_belief_from_cohorts_oracle`` (ADR 0092)."""
    return shelf_belief_from_cohorts_oracle(cohorts, empty_tau_grid=_EMPTY_TAU_GRID)


def _p1_belief(rbpf: RBPF) -> ShelfBelief:
    """P1 ShelfBelief via ``shelf_belief_from_rbpf`` after initialize/step."""
    if rbpf._state is None:
        return _empty_shelf_belief()
    return shelf_belief_from_rbpf(rbpf)


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    arr = np.asarray(list(values), dtype=float)
    return float(np.percentile(arr, q))


def _empirical_l_stats(episode: EpisodeLog) -> dict[str, float]:
    ls = [float(d.L) for d in episode.scored] or [float(d.L) for d in episode.days]
    return {
        "p50": _percentile(ls, 50),
        "p90": _percentile(ls, 90),
        "max": float(max(ls)) if ls else 0.0,
        "mean": float(np.mean(ls)) if ls else 0.0,
    }


def _run_closed_loop(
    *,
    mode: BeliefMode,
    policy: Any,
    shipments: Sequence[ShipmentTrace],
    params: ModelParams,
    root_seed: int,
    run_id: str,
    n_burn: int,
    n_score: int,
    lead_time: int,
    filter_n: int,
) -> EpisodeLog:
    """Policy-driven forward sim sharing ``model.day_step`` + ShelfBelief factories."""
    ships = list(shipments)
    cohorts: list[Cohort] = []
    next_lot_id = 1
    pending: dict[int, int] = {}
    log = EpisodeLog(n_burn=n_burn, n_score=n_score)
    horizon = n_burn + n_score

    rbpf: RBPF | None = None
    if mode == "P1":
        rbpf = RBPF(params=params, N=int(filter_n))
        rbpf._root_seed = int(root_seed)
        rbpf._run_id = run_id
        init_rng = spawn_rng(
            int(root_seed), run_id=run_id, day=0, stream=STREAM_FILTER_RESAMPLE
        )
        rbpf.initialize(init_rng)

    for day in range(horizon):
        pending_view: Mapping[int, int] = dict(pending)
        if mode == "P1":
            assert rbpf is not None
            belief: ShelfBelief | object | None = _p1_belief(rbpf)
        elif mode == "B-state":
            belief = _oracle_belief(cohorts)
        else:
            # Rung 0: age-blind; still build an oracle belief for Protocol shape.
            belief = _oracle_belief(cohorts)

        if mode == "Rung 0":
            belief_for_order: object | None = belief
        else:
            belief_for_order = (
                belief if isinstance(belief, ShelfBelief) else _empty_shelf_belief()
            )
        raw_qty = invoke_order(policy, day, belief_for_order, pending_view)

        order_units = case_round(raw_qty, params.case_size)
        pending[day + lead_time] = pending.get(day + lead_time, 0) + order_units

        arrival_units = int(pending.pop(day, 0))
        delivery: Cohort | None = None
        age_at_receipt: float | None = None
        pack_date: date | None = None
        if arrival_units > 0:
            rng_ship = spawn_rng(
                root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SHIP
            )
            rng_sensor = spawn_rng(
                root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SENSOR
            )
            tau_in = generate_arrival_age(rng_ship, rng_sensor, ships, params)
            delivery = Cohort(n=arrival_units, tau=tau_in, lot_id=next_lot_id)
            next_lot_id += 1
            age_at_receipt = float(tau_in)
            receipt_day = _EPISODE_CALENDAR_EPOCH + timedelta(days=day)
            transit_days = max(round(age_at_receipt), 0)
            pack_date = receipt_day - timedelta(days=transit_days)

        pre_live_ids = [c.lot_id for c in cohorts if c.n > 0]
        rng_d = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_DEMAND)
        rng_a = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_ALLOC)
        rng_s = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_SPOIL)
        result = day_step(
            cohorts,
            params=params,
            delivery=delivery,
            rng_demand=rng_d,
            rng_alloc=rng_a,
            rng_spoil=rng_s,
        )
        cohorts = result.cohorts
        lots = [LotState(n=c.n, tau=c.tau, lot_id=c.lot_id) for c in cohorts]
        sales_by_lot = {
            int(pre_live_ids[i]): int(result.sales_by_cohort[i])
            for i in range(len(pre_live_ids))
            if int(result.sales_by_cohort[i]) != 0
        }
        waste_by_lot = {
            int(pre_live_ids[i]): int(result.waste_by_cohort[i])
            for i in range(len(pre_live_ids))
            if int(result.waste_by_cohort[i]) != 0
        }
        day_log = DayLog(
            day=day,
            lots=lots,
            sales_total=result.sales_total,
            waste_total=result.waste_total,
            arrivals=arrival_units,
            order_qty=order_units,
            demand=result.demand,
            L=len(lots),
            sales_by_lot=sales_by_lot,
            waste_by_lot=waste_by_lot,
            age_at_receipt=age_at_receipt,
            pack_date=pack_date,
        )
        log.days.append(day_log)

        if mode == "P1" and rbpf is not None:
            obs = P1Obs(
                sales_total=int(result.sales_total),
                waste_total=int(result.waste_total),
                arrivals=int(arrival_units),
            )
            step_rng = spawn_rng(
                int(root_seed),
                run_id=run_id,
                day=day,
                stream=STREAM_FILTER_RESAMPLE,
            )
            rbpf.step(obs, step_rng)

    return log


def _write_report(
    path: Path,
    *,
    profits: Mapping[str, float],
    empirical_l: Mapping[str, float],
    root_seed: int,
    n_burn: int,
    n_score: int,
    n_rollout_paths: int,
    H: int,
    production_backend: str,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# M2 multi-scenario closed-loop + empirical L remeasure (T-033)",
        "",
        f"**root_seed:** `{root_seed}`  ",
        f"**replication:** 1 (CI smoke: n_burn={n_burn}, n_score={n_score}, "
        f"H={H}, n_rollout_paths={n_rollout_paths})",
        "",
        "## Production age backend",
        "",
        f"Production age backend remains {production_backend} "
        "(T-021 / ADR 0091). This report does not recommend a silent "
        "revert to joint; no silent joint revert.",
        "",
        "## Primary scenarios (P1 vs B-state vs Rung 0)",
        "",
        "| Scenario | Closed-loop profit |",
        "| --- | ---: |",
    ]
    for name in PRIMARY_SCENARIOS:
        lines.append(f"| {name} | {float(profits[name]):.4f} |")
    lines.extend(
        [
            "",
            "## Empirical L under SW+rollout",
            "",
            "Remeasured live-cohort **L** under the documented controller config "
            "**SW+rollout** (damped survival-weighted base + one-step rollout):",
            "",
            f"- empirical L p50 = {float(empirical_l.get('p50', 0.0)):.2f}",
            f"- empirical L p90 = {float(empirical_l.get('p90', 0.0)):.2f}",
            f"- empirical L max = {float(empirical_l.get('max', 0.0)):.2f}",
            f"- empirical L mean = {float(empirical_l.get('mean', 0.0)):.2f}",
            "",
            "Other masks (P0 / F1 / F1s / F2a / F2): interface smoke only — "
            "no full profit claims in this MD.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_m2_multi_scenario(
    *,
    root_seed: int,
    out_dir: str | Path | None = None,
    params: ModelParams | None = None,
    costs: ProfitCosts | None = None,
    shipments: Sequence[ShipmentTrace] | None = None,
    n_burn: int = _CI_N_BURN,
    n_score: int = _CI_N_SCORE,
    n_rollout_paths: int = _CI_N_ROLLOUT_PATHS,
    H: int = _CI_ROLLOUT_H,
    lead_time: int = 1,
    alpha: float = _DEFAULT_ALPHA,
    filter_n: int = _CI_FILTER_N,
    include_other_masks: bool = False,
) -> MultiScenarioResult:
    """Compare P1 / B-state / Rung 0 closed-loop; record L under SW+rollout.

    Writes a short MD under ``experiments/`` (or ``out_dir``). Production
    backend is locked to ``counts_only`` (ADR 0105).
    """
    if PRODUCTION_BACKEND != "counts_only":
        msg = (
            "multi-scenario requires production backend counts_only "
            f"(got {PRODUCTION_BACKEND!r})"
        )
        raise RuntimeError(msg)
    backend = MULTI_SCENARIO_PRODUCTION_BACKEND

    p = params or ModelParams()
    cost = costs if costs is not None else DEFAULT_PROFIT_COSTS
    ships = list(shipments) if shipments is not None else default_shipments()

    sw = DampedSurvivalWeightedPolicy(alpha=float(alpha), params=p)
    d_star = _protection_demand_fractile(float(alpha), p)
    rung0 = CorrectedAgeBlindPolicy(
        alpha=float(alpha),
        params=p,
        demand_target=d_star,
        protection_days=PROTECTION_DEMAND_DAYS,
        case_size=int(p.case_size),
    )
    rollout = RolloutPolicy(
        base_policy=sw,
        params=p,
        root_seed=int(root_seed),
        run_id="m2-multi-sw-rollout",
        H=int(H),
        n_rollout_paths=int(n_rollout_paths),
        lead_time=int(lead_time),
    )

    profits: dict[str, float] = {}
    # P1: SW policy sees RBPF MF belief.
    ep_p1 = _run_closed_loop(
        mode="P1",
        policy=sw,
        shipments=ships,
        params=p,
        root_seed=int(root_seed),
        run_id="m2-multi-p1",
        n_burn=int(n_burn),
        n_score=int(n_score),
        lead_time=int(lead_time),
        filter_n=int(filter_n),
    )
    profits["P1"] = float(episode_profit(ep_p1, cost))

    # B-state: SW policy sees oracle ShelfBelief.
    ep_b = _run_closed_loop(
        mode="B-state",
        policy=sw,
        shipments=ships,
        params=p,
        root_seed=int(root_seed),
        run_id="m2-multi-bstate",
        n_burn=int(n_burn),
        n_score=int(n_score),
        lead_time=int(lead_time),
        filter_n=int(filter_n),
    )
    profits["B-state"] = float(episode_profit(ep_b, cost))

    # Rung 0: corrected age-blind competitor.
    ep_r0 = _run_closed_loop(
        mode="Rung 0",
        policy=rung0,
        shipments=ships,
        params=p,
        root_seed=int(root_seed),
        run_id="m2-multi-rung0",
        n_burn=int(n_burn),
        n_score=int(n_score),
        lead_time=int(lead_time),
        filter_n=int(filter_n),
    )
    profits["Rung 0"] = float(episode_profit(ep_r0, cost))

    # Empirical L under SW+rollout (FIL-13 follow-up / documented CTL config).
    ep_roll = _run_closed_loop(
        mode="B-state",
        policy=rollout,
        shipments=ships,
        params=p,
        root_seed=int(root_seed),
        run_id="m2-multi-sw-rollout",
        n_burn=int(n_burn),
        n_score=int(n_score),
        lead_time=int(lead_time),
        filter_n=int(filter_n),
    )
    empirical_l = _empirical_l_stats(ep_roll)

    if out_dir is not None:
        report = Path(out_dir) / "m2_multi_scenario_result.md"
    else:
        report = Path(DEFAULT_MULTI_SCENARIO_REPORT_PATH)
    written = _write_report(
        report,
        profits=profits,
        empirical_l=empirical_l,
        root_seed=int(root_seed),
        n_burn=int(n_burn),
        n_score=int(n_score),
        n_rollout_paths=int(n_rollout_paths),
        H=int(H),
        production_backend=backend,
    )

    other_smoke: Mapping[str, bool] | None = None
    if include_other_masks:
        other_smoke = smoke_other_masks()

    return MultiScenarioResult(
        scenarios=PRIMARY_SCENARIOS,
        profits=profits,
        production_backend=backend,
        artifact_paths=(written,),
        empirical_l=empirical_l,
        root_seed=int(root_seed),
        report_path=written,
        other_mask_smoke=other_smoke,
    )

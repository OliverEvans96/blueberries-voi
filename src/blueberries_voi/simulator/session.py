"""Interactive ``EngineSession`` façade (Snapshot / DayDelta / act)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from blueberries_voi.controller.ordering import ConstantOrderPolicy
from blueberries_voi.controller.rollout import rollout_order
from blueberries_voi.filter.belief import ShelfBelief, shelf_belief_from_rbpf
from blueberries_voi.filter.rbpf import RBPF
from blueberries_voi.filter.types import mask_for
from blueberries_voi.model import ModelParams
from blueberries_voi.model.demand_profile import DemandProfile, load_demand_profile
from blueberries_voi.rng import STREAM_FILTER_RESAMPLE, spawn_rng
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule
from blueberries_voi.simulator.belief import (
    empty_flat_belief,
    live_lots_payload,
    pipeline_payload,
    shelf_belief_from_flat,
)
from blueberries_voi.simulator.day_driver import (
    DayDriverState,
    advance_day,
    build_day_delta,
    current_belief_flat,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from blueberries_voi.filter.types import ScenarioId
    from blueberries_voi.model.abdella import ShipmentTrace
    from blueberries_voi.simulator.belief import DayDelta, Snapshot

# ADR 0099 dialed browser demo preset (≤ production / desktop defaults).
DEMO_BUDGETS: dict[str, int] = {
    "n_particles": 200,
    "H": 7,
    "n_rollout_paths": 2,
    "candidate_case_radius": 1,
}

BROWSER_DEMO_BUDGETS = DEMO_BUDGETS

_HISTORY_WINDOW = 14
# ASN / OrderSchedule epoch (monday0); keep as ISO date for Studio weekday labels.
_SCHEDULE_EPOCH = "2024-01-01"


def schedule_wire(schedule: OrderSchedule | None = None) -> dict[str, Any]:
    """Export OrderSchedule fields for Snapshot / Studio calendar chrome (T-085)."""
    sched = DEFAULT_ORDER_SCHEDULE if schedule is None else schedule
    return {
        "delivery_weekdays": sorted(int(d) for d in sched.delivery_weekdays),
        "order_weekdays": sorted(int(d) for d in sched.order_weekdays),
        "lead_time_days": int(sched.lead_time_days),
        "epoch": _SCHEDULE_EPOCH,
    }


def _default_demand_profile_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "freshnet" / "demand_profile.json"


@lru_cache(maxsize=1)
def _committed_demand_profile() -> DemandProfile:
    return load_demand_profile(_default_demand_profile_path())


def demand_summary_wire(profile: DemandProfile | None = None) -> dict[str, Any]:
    """Chart-ready demand summary (scale + length-7 DOW means); not the full blob."""
    prof = _committed_demand_profile() if profile is None else profile
    scale = float(prof.scale_target_mu)
    return {
        "scale_mu": scale,
        "dow_means": [scale * float(f) for f in prof.dow_factors],
    }


class EngineSession:
    """Host-agnostic interactive session: init / step / step_n / reset / act.

    Returns ADR 0100 Snapshot and DayDelta dicts only (no ViewModel, economics,
    PnL, ghost, or heatmap). Belief crosses the wire as flat buffers.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._config: dict[str, Any] = {}
        self._seed: int = 0
        self._seq: int = 0
        self._params = ModelParams()
        self._shipments: list[ShipmentTrace] = []
        self._lead_time: int = 1
        self._enable_filter: bool = True
        self._obs_scenario: ScenarioId | str = "P1"
        self._L: int = 2
        self._K: int = 4
        self._n_particles: int = int(DEMO_BUDGETS["n_particles"])
        self._H: int = int(DEMO_BUDGETS["H"])
        self._n_rollout_paths: int = int(DEMO_BUDGETS["n_rollout_paths"])
        self._candidate_case_radius: int = int(DEMO_BUDGETS["candidate_case_radius"])
        self._history: list[dict[str, Any]] = []
        self._state = DayDriverState(
            cohorts=[],
            pending={},
            next_lot_id=1,
            episode_day=0,
            rbpf=None,
        )

    def init(
        self,
        config: Mapping[str, Any],
        *,
        seed: int | None = None,
    ) -> Snapshot:
        """Cold-start the session from ``config``; return a Snapshot."""
        self._apply_config(dict(config), seed=seed)
        self._boot_state()
        self._initialized = True
        self._seq = 0
        self._history = []
        return self._snapshot()

    def reset(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        seed: int | None = None,
    ) -> Snapshot:
        """Re-initialize; omit ``config`` to reuse the last applied mapping."""
        if config is None:
            if not self._config:
                msg = "reset() without config requires a prior init()"
                raise RuntimeError(msg)
            cfg = dict(self._config)
        else:
            cfg = dict(config)
        return self.init(cfg, seed=seed if seed is not None else self._seed)

    def step(self, order_qty: int) -> DayDelta:
        """Advance one day with an explicit order quantity."""
        self._require_init()
        if not isinstance(order_qty, int) or isinstance(order_qty, bool):
            msg = f"order_qty must be an int, got {type(order_qty)!r}"
            raise TypeError(msg)
        return self._advance(int(order_qty))

    def step_n(self, orders: Sequence[int]) -> list[DayDelta]:
        """Advance ``k`` days; returns exactly ``k`` DayDelta dicts."""
        self._require_init()
        return [self.step(int(q)) for q in orders]

    def act(
        self,
        *,
        policy: str | None = None,
        **budget_overrides: Any,
    ) -> DayDelta:
        """Select an order via the controller surface and advance one day."""
        self._require_init()
        order_qty = self._select_order(policy=policy, **budget_overrides)
        return self._advance(int(order_qty))

    def _require_init(self) -> None:
        if not self._initialized:
            msg = "EngineSession.init() must be called before step/act"
            raise RuntimeError(msg)

    def _apply_config(self, config: dict[str, Any], *, seed: int | None) -> None:
        shipments = config.get("shipments")
        if not shipments:
            msg = (
                "config['shipments'] must be a non-empty sequence "
                "(injectable; no parquet)"
            )
            raise ValueError(msg)
        self._shipments = list(shipments)
        self._config = dict(config)
        self._seed = 0 if seed is None else int(seed)
        self._params = ModelParams()
        self._lead_time = int(config.get("lead_time", 1))
        self._enable_filter = bool(config.get("enable_filter", True))
        raw_scenario = config.get("obs_scenario", "P1")
        # Validate via mask_for spirit (unknown / B-state raise).
        mask_for(raw_scenario)
        self._obs_scenario = raw_scenario
        self._L = int(config.get("L", self._L))
        self._K = int(config.get("K", self._K))
        self._n_particles = int(config.get("n_particles", self._n_particles))
        self._H = int(config.get("H", self._H))
        self._n_rollout_paths = int(
            config.get("n_rollout_paths", self._n_rollout_paths)
        )
        self._candidate_case_radius = int(
            config.get("candidate_case_radius", self._candidate_case_radius)
        )

    def _boot_state(self) -> None:
        rbpf: RBPF | None = None
        if self._enable_filter:
            rbpf = RBPF(
                params=self._params,
                N=int(self._n_particles),
                K=int(self._K),
                L=int(self._L),
            )
            rbpf._root_seed = int(self._seed)
            rbpf._run_id = "session"
            init_rng = spawn_rng(
                int(self._seed),
                run_id="session",
                day=0,
                stream=STREAM_FILTER_RESAMPLE,
            )
            rbpf.initialize(init_rng, L=int(self._L))
        self._state = DayDriverState(
            cohorts=[],
            pending={},
            next_lot_id=1,
            episode_day=0,
            rbpf=rbpf,
        )

    def _applied_config(self) -> dict[str, Any]:
        return {
            "n_particles": int(self._n_particles),
            "H": int(self._H),
            "n_rollout_paths": int(self._n_rollout_paths),
            "candidate_case_radius": int(self._candidate_case_radius),
            "L": int(self._L),
            "K": int(self._K),
            "enable_filter": bool(self._enable_filter),
            "lead_time": int(self._lead_time),
            "obs_scenario": self._obs_scenario,
            "seed": int(self._seed),
        }

    def _belief_for_snapshot(self) -> dict[str, Any]:
        return dict(
            current_belief_flat(
                self._state,
                enable_filter=self._enable_filter,
                L=self._L,
                K=self._K,
            )
        )

    def _snapshot(self) -> Snapshot:
        return {
            "seq": int(self._seq),
            "episode_day": int(self._state.episode_day),
            "applied_config": self._applied_config(),
            "history": list(self._history),
            "belief": self._belief_for_snapshot(),
            "live_lots": live_lots_payload(self._state.cohorts),
            "pipeline": pipeline_payload(self._state.pending),
            "schedule": schedule_wire(),
            "demand_summary": demand_summary_wire(),
        }

    def _advance(self, order_qty: int) -> DayDelta:
        completed_day = int(self._state.episode_day)
        result = advance_day(
            self._state,
            order_qty,
            shipments=self._shipments,
            params=self._params,
            root_seed=self._seed,
            run_id="session",
            lead_time=self._lead_time,
            enable_filter=self._enable_filter,
            obs_scenario=self._obs_scenario,
        )
        self._state = result.state
        self._seq += 1
        drop_oldest = len(self._history) >= _HISTORY_WINDOW
        if drop_oldest and self._history:
            self._history.pop(0)
        self._history.append(dict(result.day))
        return build_day_delta(
            seq=self._seq,
            episode_day=completed_day,
            result=result,
            drop_oldest=drop_oldest,
        )

    def _select_order(self, *, policy: str | None, **budget_overrides: Any) -> int:
        n_particles = int(budget_overrides.get("n_particles", self._n_particles))
        horizon = int(budget_overrides.get("H", self._H))
        n_paths = int(budget_overrides.get("n_rollout_paths", self._n_rollout_paths))
        radius = int(
            budget_overrides.get("candidate_case_radius", self._candidate_case_radius)
        )
        self._n_particles = n_particles
        self._H = horizon
        self._n_rollout_paths = n_paths
        self._candidate_case_radius = radius

        name = (policy or "constant").lower()
        day = int(self._state.episode_day)
        pending = dict(self._state.pending)
        belief = self._belief_for_policy()

        if name in {"constant", "const", "fixed"}:
            q = budget_overrides.get("order_qty", budget_overrides.get("q", 0))
            policy_obj = ConstantOrderPolicy(int(q), case_size=self._params.case_size)
            return int(
                policy_obj.order(
                    belief,
                    day=day,
                    pending_orders=pending,  # type: ignore[arg-type]
                )
            )

        if name in {"rollout", "ctl", "rollout_order"}:
            base = ConstantOrderPolicy(0, case_size=self._params.case_size)
            return int(
                rollout_order(
                    belief,
                    # ConstantOrderPolicy.order pending_orders typing is tuple;
                    # runtime accepts Mapping (unused). Match CTL protocol via cast.
                    base_policy=cast("Any", base),
                    day=day,
                    pending_orders=pending,
                    params=self._params,
                    rng_address={
                        "root_seed": self._seed,
                        "run_id": "session-act",
                    },
                    H=horizon,
                    n_rollout_paths=n_paths,
                    candidate_case_radius=radius,
                    n_particles=n_particles,
                )
            )

        msg = f"unknown policy {policy!r}; use 'constant' or 'rollout'"
        raise ValueError(msg)

    def _belief_for_policy(self) -> ShelfBelief:
        if (
            self._enable_filter
            and self._state.rbpf is not None
            and self._state.rbpf._state is not None
        ):
            return shelf_belief_from_rbpf(self._state.rbpf)
        return shelf_belief_from_flat(empty_flat_belief(L=self._L, K=self._K))


__all__ = [
    "BROWSER_DEMO_BUDGETS",
    "DEMO_BUDGETS",
    "EngineSession",
    "demand_summary_wire",
    "schedule_wire",
]

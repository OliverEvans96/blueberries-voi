"""Interactive ``EngineSession`` façade (Snapshot / DayDelta / act)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from blueberries_voi.controller.damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.controller.ordering import ConstantOrderPolicy, invoke_order
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
        self._rust: Any | None = None
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
        self._initialized = True
        self._seq = 0
        self._history = []
        if self._rust_backend():
            return self._init_rust()
        self._boot_state()
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
        if self._rust is not None:
            raw = self._rust.step(int(order_qty))
            self._seq += 1
            return self._coerce_day_delta(raw, seq=self._seq)
        return self._advance(int(order_qty))

    def step_n(self, orders: Sequence[int]) -> list[DayDelta]:
        """Advance ``k`` days; returns exactly ``k`` DayDelta dicts."""
        self._require_init()
        qty = [int(q) for q in orders]
        if self._rust is not None:
            raw = self._rust.step_n(qty)
            if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
                msg = "rust step_n must return a sequence of DayDeltas"
                raise TypeError(msg)
            out: list[DayDelta] = []
            for item in raw:
                self._seq += 1
                out.append(self._coerce_day_delta(item, seq=self._seq))
            return out
        return [self.step(q) for q in qty]

    def act(
        self,
        *,
        policy: str | None = None,
        **budget_overrides: Any,
    ) -> DayDelta:
        """Select an order via the controller surface and advance one day."""
        self._require_init()
        if self._rust is not None:
            act_fn = getattr(self._rust, "act", None)
            raw = (
                act_fn(policy, **budget_overrides)
                if callable(act_fn)
                else self._rust.act_rollout()
            )
            self._seq += 1
            return self._coerce_day_delta(raw, seq=self._seq)
        order_qty = self._select_order(policy=policy, **budget_overrides)
        return self._advance(int(order_qty))

    def host_crossings(self) -> int:
        """Host/FFI crossings (Rust backend) or Python step count."""
        if self._rust is not None:
            return int(self._rust.host_crossings())
        return int(self._seq)

    def _require_init(self) -> None:
        if not self._initialized:
            msg = "EngineSession.init() must be called before step/act"
            raise RuntimeError(msg)

    def _rust_backend(self) -> bool:
        from blueberries_voi.backend import rust_available, warn_fallback_once

        warn_fallback_once()
        return rust_available()

    def _init_rust(self) -> Snapshot:
        from blueberries_voi.backend import rust_core

        if rust_core is None:
            self._boot_state()
            return self._snapshot()
        cls = getattr(rust_core, "PyEngineSession", None)
        if cls is None:
            self._boot_state()
            return self._snapshot()
        if self._rust is None:
            self._rust = cls(int(self._seed))
        sess = self._rust
        times = [list(map(float, getattr(s, "times_d", []))) for s in self._shipments]
        temps = [list(map(float, getattr(s, "temps_c", []))) for s in self._shipments]
        init_fn = sess.init
        try:
            raw = init_fn(
                int(self._seed),
                int(self._lead_time),
                bool(self._enable_filter),
                int(self._H),
                int(self._n_rollout_paths),
                int(self._candidate_case_radius),
                times,
                temps,
            )
        except TypeError:
            raw = init_fn(int(self._seed))
        return self._coerce_snapshot(raw)

    def _coerce_snapshot(self, raw: Any) -> Snapshot:
        if isinstance(raw, Mapping) and "belief" in raw:
            snap = dict(raw)
            snap.setdefault("seq", 0)
            snap.setdefault("episode_day", 0)
            snap.setdefault("schedule", schedule_wire())
            snap.setdefault("demand_summary", demand_summary_wire())
            snap.setdefault("applied_config", self._applied_config())
            snap.setdefault("history", [])
            snap.setdefault("live_lots", [])
            snap.setdefault("pipeline", [])
            return snap
        self._boot_state()
        return self._snapshot()

    def _coerce_day_delta(self, raw: Any, *, seq: int) -> DayDelta:
        if isinstance(raw, Mapping) and "day" in raw:
            delta = dict(raw)
            delta["seq"] = int(raw.get("seq", seq))
            delta.setdefault("episode_day", 0)
            return delta
        episode_day = int(getattr(raw, "episode_day", 0))
        order_qty = int(getattr(raw, "order_qty", 0))
        arrivals = int(getattr(raw, "arrivals", 0))
        sales = int(getattr(raw, "sales_total", 0))
        waste = int(getattr(raw, "waste_total", 0))
        demand = int(getattr(raw, "demand", 0))
        on_hand = int(getattr(raw, "on_hand", 0))
        return {
            "seq": int(seq),
            "episode_day": episode_day,
            "day": {
                "day": episode_day,
                "order_qty": order_qty,
                "arrivals": arrivals,
                "sales_total": sales,
                "waste_total": waste,
                "demand": demand,
                "L": on_hand,
            },
            "live_lots": [],
            "pipeline": [],
            "drop_oldest": False,
            "belief": dict(empty_flat_belief(L=self._L, K=self._K)),
        }

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
        alpha = float(budget_overrides.get("alpha", 0.9))
        rho = float(budget_overrides.get("rho", 0.8))

        if name in {"constant", "const", "fixed"}:
            q = budget_overrides.get("order_qty", budget_overrides.get("q", 0))
            policy_obj = ConstantOrderPolicy(int(q), case_size=self._params.case_size)
            return invoke_order(policy_obj, day, belief, pending)

        if name in {"damped_sw", "sw"}:
            sw_policy = DampedSurvivalWeightedPolicy(
                alpha=alpha,
                rho=rho,
                params=self._params,
            )
            return invoke_order(sw_policy, day, belief, pending)

        if name in {"rollout", "ctl", "rollout_order"}:
            base = DampedSurvivalWeightedPolicy(
                alpha=alpha,
                rho=rho,
                params=self._params,
            )
            return int(
                rollout_order(
                    belief,
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

        msg = f"unknown policy {policy!r}; use 'damped_sw', 'constant', or 'rollout'"
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

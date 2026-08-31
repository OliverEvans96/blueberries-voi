"""Interactive ``EngineSession`` façade (Snapshot / DayDelta / act).

Wave F (T-121 / ADR 0127): PyO3 dispatch and wire coercion only — no Python
physics loop, ``day_driver``, or ``model.day_step`` on the production path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from blueberries_voi.filter.types import (
    ObsChannels,
    mask_for,
    preset_for_channels,
    validate_channels,
)
from blueberries_voi.model.demand_profile import DemandProfile, load_demand_profile
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule

if TYPE_CHECKING:
    from blueberries_voi.filter.types import ScenarioId
    from blueberries_voi.model.abdella import ShipmentTrace
    from blueberries_voi.simulator.belief import DayDelta, Snapshot

DEMO_BUDGETS: dict[str, int] = {
    "n_particles": 200,
    "H": 7,
    "n_rollout_paths": 2,
    "candidate_case_radius": 1,
}

BROWSER_DEMO_BUDGETS = DEMO_BUDGETS

EPISODE_HORIZON = 90
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

    Returns ADR 0100 Snapshot and DayDelta dicts only. All hot compute is delegated
    to ``blueberries_voi._core.PyEngineSession`` when ``BLUEBERRIES_VOI_BACKEND=rust``.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._config: dict[str, Any] = {}
        self._seed: int = 0
        self._seq: int = 0
        self._shipments: list[ShipmentTrace] = []
        self._lead_time: int = 1
        self._delivery_weekdays: frozenset[int] = (
            DEFAULT_ORDER_SCHEDULE.delivery_weekdays
        )
        self._schedule: OrderSchedule = DEFAULT_ORDER_SCHEDULE
        self._enable_filter: bool = True
        self._belief_source: str = "filter"
        self._obs_scenario: ScenarioId | str = "P1"
        self._L: int = 10
        self._K: int = 30
        self._n_particles: int = int(DEMO_BUDGETS["n_particles"])
        self._H: int = int(DEMO_BUDGETS["H"])
        self._n_rollout_paths: int = int(DEMO_BUDGETS["n_rollout_paths"])
        self._candidate_case_radius: int = int(DEMO_BUDGETS["candidate_case_radius"])
        self._rust: Any | None = None

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
        sess = self._require_rust()
        times = [list(map(float, getattr(s, "times_d", []))) for s in self._shipments]
        temps = [list(map(float, getattr(s, "temps_c", []))) for s in self._shipments]
        init_fn = sess.init
        delivery = sorted(int(d) for d in self._delivery_weekdays)
        belief_source = str(self._belief_source)
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
                int(self._n_particles),
                int(self._L),
                int(self._K),
                str(self._obs_scenario),
                None,
                delivery,
                None,
                belief_source,
            )
        except TypeError:
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
                    int(self._n_particles),
                    int(self._L),
                    int(self._K),
                    str(self._obs_scenario),
                    None,
                    delivery,
                    None,
                )
            except TypeError:
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
                        int(self._n_particles),
                        int(self._L),
                        int(self._K),
                        str(self._obs_scenario),
                        None,
                    )
                except TypeError:
                    raw = init_fn(
                        int(self._seed),
                        int(self._lead_time),
                        bool(self._enable_filter),
                        int(self._H),
                        int(self._n_rollout_paths),
                        int(self._candidate_case_radius),
                        times,
                        temps,
                        int(self._n_particles),
                    )
        return self._coerce_snapshot(raw)

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
        self._refuse_if_episode_ended(n_days=1)
        raw = self._require_rust().step(int(order_qty))
        self._seq += 1
        return self._coerce_day_delta(raw, seq=self._seq)

    def step_n(self, orders: Sequence[int]) -> list[DayDelta]:
        """Advance ``k`` days; returns exactly ``k`` DayDelta dicts."""
        self._require_init()
        qty = [int(q) for q in orders]
        self._refuse_if_episode_ended(n_days=len(qty))
        raw = self._require_rust().step_n(qty)
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            msg = "rust step_n must return a sequence of DayDeltas"
            raise TypeError(msg)
        out: list[DayDelta] = []
        for item in raw:
            self._seq += 1
            out.append(self._coerce_day_delta(item, seq=self._seq))
        return out

    def act(
        self,
        *,
        policy: str | None = None,
        **budget_overrides: Any,
    ) -> DayDelta:
        """Select an order via the controller surface and advance one day."""
        self._require_init()
        self._refuse_if_episode_ended(n_days=1)
        sess = self._require_rust()
        act_fn = getattr(sess, "act", None)
        raw = (
            act_fn(policy, **budget_overrides)
            if callable(act_fn)
            else sess.act_rollout()
        )
        self._seq += 1
        return self._coerce_day_delta(raw, seq=self._seq)

    def set_obs_scenario(self, obs_scenario: ScenarioId | str) -> Snapshot:
        """Catch-up the selected observation preset and return a Snapshot."""
        self._require_init()
        mask_for(obs_scenario)
        self._obs_scenario = obs_scenario
        self._config["obs_scenario"] = obs_scenario
        fn = getattr(self._require_rust(), "set_obs_scenario", None)
        if not callable(fn):
            msg = "PyEngineSession.set_obs_scenario is required after T-121 Wave F"
            raise RuntimeError(msg)
        return self._coerce_snapshot(fn(str(obs_scenario)))

    def set_obs_channels(self, channels: ObsChannels | Mapping[str, str]) -> Snapshot:
        """Catch-up the selected observation channels and return a Snapshot."""
        self._require_init()
        ch = validate_channels(channels)
        self._config["obs_channels"] = {
            "code_type": ch.code_type,
            "scan_waste": ch.scan_waste,
            "delivery_history": ch.delivery_history,
        }
        preset = preset_for_channels(ch)
        if preset is not None:
            self._obs_scenario = preset
            self._config["obs_scenario"] = preset
        fn = getattr(self._require_rust(), "set_obs_channels", None)
        if not callable(fn):
            msg = "PyEngineSession.set_obs_channels is required after T-128"
            raise RuntimeError(msg)
        return self._coerce_snapshot(
            fn(ch.code_type, ch.scan_waste, ch.delivery_history)
        )

    def snapshot(self) -> Snapshot:
        """Current session state without advancing (Rust ``snapshot_value``)."""
        self._require_init()
        raw = self._require_rust().snapshot_value()
        return self._coerce_snapshot(raw)

    def host_crossings(self) -> int:
        """Host/FFI crossings (Rust backend)."""
        return int(self._require_rust().host_crossings())

    def _require_init(self) -> None:
        if not self._initialized:
            msg = "EngineSession.init() must be called before step/act"
            raise RuntimeError(msg)

    def _refuse_if_episode_ended(self, *, n_days: int) -> None:
        if n_days <= 0:
            return
        if self._seq >= EPISODE_HORIZON or self._seq + n_days > EPISODE_HORIZON:
            msg = (
                f"episode ended at day {EPISODE_HORIZON}; Reset to start a new episode"
            )
            raise ValueError(msg)

    def _require_rust(self) -> Any:
        from blueberries_voi.backend import (
            rust_available,
            rust_core,
            warn_fallback_once,
        )

        warn_fallback_once()
        if not rust_available() or rust_core is None:
            msg = (
                "EngineSession requires BLUEBERRIES_VOI_BACKEND=rust and "
                "blueberries_voi._core (T-121 Wave F)"
            )
            raise RuntimeError(msg)
        if self._rust is None:
            cls = getattr(rust_core, "PyEngineSession", None)
            if cls is None:
                msg = "PyEngineSession missing from blueberries_voi._core"
                raise RuntimeError(msg)
            self._rust = cls(int(self._seed))
        return self._rust

    def _coerce_snapshot(self, raw: Any) -> Snapshot:
        if isinstance(raw, Mapping) and "belief" in raw:
            snap = dict(raw)
            snap.setdefault("seq", 0)
            snap.setdefault("episode_day", 0)
            snap.setdefault("schedule", schedule_wire(self._schedule))
            snap.setdefault("demand_summary", demand_summary_wire())
            snap.setdefault("applied_config", self._applied_config())
            snap.setdefault("history", [])
            snap.setdefault("live_lots", [])
            snap.setdefault("pipeline", [])
            return snap
        msg = "PyEngineSession.init/reset must return a Snapshot mapping"
        raise TypeError(msg)

    def _coerce_day_delta(self, raw: Any, *, seq: int) -> DayDelta:
        if isinstance(raw, Mapping) and "day" in raw:
            delta = dict(raw)
            delta["seq"] = int(raw.get("seq", seq))
            delta.setdefault("episode_day", 0)
            return delta
        msg = "PyEngineSession step/act must return a DayDelta mapping"
        raise TypeError(msg)

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
        self._lead_time = int(config.get("lead_time", 1))
        raw_delivery = config.get("delivery_weekdays")
        if raw_delivery is None:
            self._delivery_weekdays = DEFAULT_ORDER_SCHEDULE.delivery_weekdays
        else:
            self._delivery_weekdays = frozenset(int(d) for d in raw_delivery)
        self._schedule = OrderSchedule.with_delivery(
            self._delivery_weekdays,
            lead_time_days=self._lead_time,
        )
        self._enable_filter = bool(config.get("enable_filter", True))
        raw_belief = str(config.get("belief_source", "filter")).strip().lower()
        if raw_belief not in {"filter", "truth"}:
            msg = f"belief_source must be 'filter' or 'truth'; got {raw_belief!r}"
            raise ValueError(msg)
        self._belief_source = raw_belief
        raw_channels = config.get("obs_channels")
        if raw_channels is not None:
            ch = validate_channels(raw_channels)
            self._config["obs_channels"] = {
                "code_type": ch.code_type,
                "scan_waste": ch.scan_waste,
                "delivery_history": ch.delivery_history,
            }
            preset = preset_for_channels(ch)
            if preset is not None:
                self._obs_scenario = preset
            else:
                raw_scenario = config.get("obs_scenario", "P1")
                mask_for(raw_scenario)
                self._obs_scenario = raw_scenario
        else:
            raw_scenario = config.get("obs_scenario", "P1")
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

    def _applied_config(self) -> dict[str, Any]:
        return {
            "n_particles": int(self._n_particles),
            "H": int(self._H),
            "n_rollout_paths": int(self._n_rollout_paths),
            "candidate_case_radius": int(self._candidate_case_radius),
            "L": int(self._L),
            "K": int(self._K),
            "enable_filter": bool(self._enable_filter),
            "belief_source": str(self._belief_source),
            "lead_time": int(self._lead_time),
            "delivery_weekdays": sorted(int(d) for d in self._delivery_weekdays),
            "obs_scenario": self._obs_scenario,
            "seed": int(self._seed),
        }


__all__ = [
    "BROWSER_DEMO_BUDGETS",
    "DEMO_BUDGETS",
    "EPISODE_HORIZON",
    "EngineSession",
    "demand_summary_wire",
    "schedule_wire",
]

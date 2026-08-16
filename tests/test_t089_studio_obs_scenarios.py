"""T-089 RED: Studio obs_scenario ≡ ScenarioId ladder + masked day_driver.

Locks `.team/specs/T-089.md` / ADR 0109. Interactive path must stop hardcoding
``P1Obs`` and wire ``mask_for`` + ``rich_obs_from_day_log``. SCN-P2 stays Out.
Ticket A chart rebin is out of scope (not asserted here).
"""

from __future__ import annotations

import pytest

pytest.skip("T-121 F3: day_driver removed", allow_module_level=True)

import ast
import importlib
import inspect
from datetime import date
from pathlib import Path
from typing import Any, get_args

import numpy as np
import pytest
from blueberries_voi.simulator.day_driver import DayDriverState, advance_day

from blueberries_voi.filter.particle.research import ResearchParticleFilter
from blueberries_voi.filter.types import (
    UNOBSERVED,
    P1Obs,
    RichObs,
    ScenarioId,
    is_unobserved,
    mask_for,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.sim.order_schedule import OrderSchedule
from blueberries_voi.simulator.session import EngineSession

_REPO = Path(__file__).resolve().parents[1]
_DAY_DRIVER_SRC = _REPO / "src" / "blueberries_voi" / "simulator" / "day_driver.py"
_TYPES_SRC = _REPO / "src" / "blueberries_voi" / "filter" / "types.py"
_BACKLOG = _REPO / ".team" / "backlog.md"
_ADR_0022 = _REPO / ".team" / "adr" / "0022-scn-p2-instrumented-store.md"

_LADDER: tuple[str, ...] = ("P0", "P1", "F1", "F1s", "F2a", "F2")


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T089-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
    ]


def _minimal_config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "shipments": _fixture_shipments(),
        "n_particles": 24,
        "H": 3,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
    }
    cfg.update(overrides)
    return cfg


def _boot_particle_filter(*, seed: int = 7) -> ResearchParticleFilter:
    particle_filter = ResearchParticleFilter(params=ModelParams(), N=24, K=4, L=2)
    particle_filter._root_seed = seed
    particle_filter._run_id = "t089"
    particle_filter.initialize(np.random.default_rng(seed), L=2)
    return particle_filter


def _fresh_state(*, seed: int = 7) -> DayDriverState:
    return DayDriverState(
        cohorts=[],
        pending={},
        next_lot_id=1,
        episode_day=0,
        particle_filter=_boot_particle_filter(seed=seed),
    )


# Daily order weekdays so T-089 isolates obs_scenario (not CAL-01 MWF gating).
_DAILY_ORDER_SCHEDULE = OrderSchedule(order_weekdays=frozenset(range(7)))


def _advance(
    state: DayDriverState,
    order_qty: int,
    *,
    obs_scenario: str = "P1",
    **kwargs: Any,
) -> Any:
    """Call advance_day; fail clearly if obs_scenario kw is not supported yet."""
    sig = inspect.signature(advance_day)
    call_kw = dict(kwargs)
    if "schedule" in sig.parameters and "schedule" not in call_kw:
        call_kw["schedule"] = _DAILY_ORDER_SCHEDULE
    if "obs_scenario" in sig.parameters:
        call_kw["obs_scenario"] = obs_scenario
    elif obs_scenario != "P1":
        pytest.fail(
            f"advance_day missing obs_scenario parameter (wanted {obs_scenario!r})"
        )
    return advance_day(state, order_qty, **call_kw)


def _capture_obs(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Capture the observation object passed into ``particle_filter.step``."""
    captured: list[Any] = []
    real_step = ResearchParticleFilter.step

    def _spy(self: ResearchParticleFilter, obs: Any, rng: Any = None) -> Any:
        captured.append(obs)
        return real_step(self, obs, rng)

    monkeypatch.setattr(ResearchParticleFilter, "step", _spy)
    session_mod = importlib.import_module("blueberries_voi.simulator.session")
    session_particle_filter = getattr(session_mod, "ResearchParticleFilter", None)
    if (
        session_particle_filter is not None
        and session_particle_filter is not ResearchParticleFilter
    ):
        monkeypatch.setattr(session_particle_filter, "step", _spy)
    return captured


# ---------------------------------------------------------------------------
# AC: EngineSession obs_scenario in applied_config; default P1; invalid raises
# ---------------------------------------------------------------------------


def test_engine_session_applied_config_echoes_obs_scenario() -> None:
    session = EngineSession()
    snap = session.init(_minimal_config(obs_scenario="F1"), seed=11)
    applied = snap["applied_config"]
    assert "obs_scenario" in applied, "Snapshot applied_config must echo obs_scenario"
    assert applied["obs_scenario"] == "F1"


def test_engine_session_default_obs_scenario_is_p1_when_omitted() -> None:
    session = EngineSession()
    snap = session.init(_minimal_config(), seed=11)
    assert "obs_scenario" not in _minimal_config()  # omitted on purpose
    applied = snap["applied_config"]
    assert "obs_scenario" in applied
    assert applied["obs_scenario"] == "P1"


def test_engine_session_reset_applies_new_obs_scenario() -> None:
    session = EngineSession()
    session.init(_minimal_config(obs_scenario="P1"), seed=3)
    snap = session.reset(_minimal_config(obs_scenario="F2"), seed=3)
    applied = snap["applied_config"]
    assert "obs_scenario" in applied
    assert applied["obs_scenario"] == "F2"


@pytest.mark.parametrize("bad_id", ["P2", "B-state", "not-a-scenario", ""])
def test_engine_session_rejects_invalid_obs_scenario(bad_id: str) -> None:
    session = EngineSession()
    with pytest.raises((ValueError, KeyError, TypeError)):
        session.init(_minimal_config(obs_scenario=bad_id), seed=1)


# ---------------------------------------------------------------------------
# AC: day_driver does not construct P1Obs; uses mask_for + rich_obs_from_day_log
# ---------------------------------------------------------------------------


def test_day_driver_source_imports_mask_and_rich_obs() -> None:
    src = _DAY_DRIVER_SRC.read_text(encoding="utf-8")
    assert "mask_for" in src, "day_driver must call mask_for(obs_scenario)"
    assert "rich_obs_from_day_log" in src, (
        "day_driver must build RichObs via rich_obs_from_day_log"
    )


def test_day_driver_source_does_not_construct_p1obs_on_filter_path() -> None:
    tree = ast.parse(_DAY_DRIVER_SRC.read_text(encoding="utf-8"))
    p1_ctors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name == "P1Obs":
                p1_ctors.append(f"line {node.lineno}")
    assert p1_ctors == [], (
        "advance_day filter path must not construct P1Obs "
        f"(found at {p1_ctors}); use mask_for + rich_obs_from_day_log"
    )


def test_advance_day_accepts_obs_scenario_kwarg() -> None:
    sig = inspect.signature(advance_day)
    assert "obs_scenario" in sig.parameters, (
        "advance_day(..., obs_scenario: ScenarioId = 'P1') required by T-089"
    )
    default = sig.parameters["obs_scenario"].default
    assert default == "P1" or default == inspect.Parameter.empty


def test_advance_day_passes_rich_obs_not_p1obs_to_particle_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_obs(monkeypatch)
    state = _fresh_state(seed=21)
    _advance(
        state,
        order_qty=16,
        shipments=_fixture_shipments(),
        params=ModelParams(),
        root_seed=21,
        run_id="t089",
        enable_filter=True,
        obs_scenario="P1",
    )
    assert captured, "particle_filter.step must run when enable_filter"
    obs = captured[-1]
    assert isinstance(obs, RichObs), (
        f"interactive path must pass RichObs to particle_filter.step, got {type(obs)!r}"
    )
    assert not isinstance(obs, P1Obs)


# ---------------------------------------------------------------------------
# AC: mask observability on interactive path (same physics, different masks)
# ---------------------------------------------------------------------------


def _run_until_filter_obs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    obs_scenario: str,
    seed: int = 42,
    days: int = 3,
    order_qty: int = 24,
) -> Any:
    """Advance a few days so delivery + sales/waste exist; return last filter obs."""
    captured = _capture_obs(monkeypatch)
    state = _fresh_state(seed=seed)
    params = ModelParams()
    ships = _fixture_shipments()
    for _ in range(days):
        result = _advance(
            state,
            order_qty=order_qty,
            shipments=ships,
            params=params,
            root_seed=seed,
            run_id="t089-mask",
            enable_filter=True,
            obs_scenario=obs_scenario,
        )
        state = result.state
    assert captured, f"expected particle_filter.step under scenario {obs_scenario!r}"
    return captured[-1]


def test_interactive_p0_masks_waste_total_unobserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    obs = _run_until_filter_obs(monkeypatch, obs_scenario="P0")
    waste = getattr(obs, "waste_total", None)
    assert is_unobserved(waste) or waste is UNOBSERVED
    assert waste != 0
    assert not isinstance(waste, (int, np.integer))


def test_interactive_p1_presents_waste_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    obs = _run_until_filter_obs(monkeypatch, obs_scenario="P1")
    waste = getattr(obs, "waste_total", UNOBSERVED)
    assert not is_unobserved(waste)
    assert isinstance(waste, (int, np.integer))


def test_interactive_f1_presents_sales_by_lot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    obs = _run_until_filter_obs(monkeypatch, obs_scenario="F1")
    sales = getattr(obs, "sales_by_lot", UNOBSERVED)
    assert not is_unobserved(sales)
    assert isinstance(sales, dict)


def test_interactive_f1s_presents_waste_by_lot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    obs = _run_until_filter_obs(monkeypatch, obs_scenario="F1s")
    waste_lots = getattr(obs, "waste_by_lot", UNOBSERVED)
    assert not is_unobserved(waste_lots)
    assert isinstance(waste_lots, dict)


def test_interactive_f2a_presents_pack_date_when_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # lead_time=1: order on day 0 arrives day 1 → pack_date on delivery day.
    captured = _capture_obs(monkeypatch)
    state = _fresh_state(seed=9)
    params = ModelParams()
    ships = _fixture_shipments()
    for day_i, qty in enumerate((32, 0, 0)):
        result = _advance(
            state,
            order_qty=qty,
            shipments=ships,
            params=params,
            root_seed=9,
            run_id="t089-f2a",
            lead_time=1,
            enable_filter=True,
            obs_scenario="F2a",
        )
        state = result.state
        if day_i == 1:
            assert captured, "filter must step on delivery day"
            obs = captured[-1]
            pack = getattr(obs, "pack_date", UNOBSERVED)
            assert not is_unobserved(pack), (
                f"F2a must present pack_date when a delivery exists (got {pack!r})"
            )
            assert isinstance(pack, date)
            return
    pytest.fail("never reached delivery day with F2a pack_date")


def test_interactive_f2_presents_age_at_receipt_and_lot_maps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_obs(monkeypatch)
    state = _fresh_state(seed=13)
    params = ModelParams()
    ships = _fixture_shipments()
    for day_i, qty in enumerate((32, 16, 0)):
        result = _advance(
            state,
            order_qty=qty,
            shipments=ships,
            params=params,
            root_seed=13,
            run_id="t089-f2",
            lead_time=1,
            enable_filter=True,
            obs_scenario="F2",
        )
        state = result.state
        if day_i >= 1 and captured:
            obs = captured[-1]
            age = getattr(obs, "age_at_receipt", UNOBSERVED)
            if not is_unobserved(age):
                assert isinstance(age, (float, int, np.floating))
                sales = getattr(obs, "sales_by_lot", UNOBSERVED)
                waste_lots = getattr(obs, "waste_by_lot", UNOBSERVED)
                assert not is_unobserved(sales) or not is_unobserved(waste_lots)
                return
    pytest.fail(
        "F2 interactive path never presented age_at_receipt + lot maps "
        "on a delivery day (richest DayLog fields missing)"
    )


def test_hidden_fields_never_invented_as_zero_or_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    obs = _run_until_filter_obs(monkeypatch, obs_scenario="P0")
    waste = getattr(obs, "waste_total", None)
    sales = getattr(obs, "sales_by_lot", UNOBSERVED)
    waste_lots = getattr(obs, "waste_by_lot", UNOBSERVED)
    assert waste != 0
    assert sales != {}
    assert waste_lots != {}
    assert is_unobserved(waste)
    assert is_unobserved(sales)
    assert is_unobserved(waste_lots)


def test_engine_session_forwards_obs_scenario_into_advance_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session must pass stored obs_scenario into advance_day (not hardcode P1)."""
    seen: list[str] = []
    import blueberries_voi.simulator.day_driver as day_driver_mod

    real = day_driver_mod.advance_day

    def _spy(*args: Any, **kwargs: Any) -> Any:
        seen.append(
            str(kwargs["obs_scenario"]) if "obs_scenario" in kwargs else "MISSING"
        )
        return real(*args, **kwargs)

    monkeypatch.setitem(EngineSession._advance.__globals__, "advance_day", _spy)
    session = EngineSession()
    session.init(_minimal_config(obs_scenario="F1s"), seed=5)
    session.step(16)
    assert seen, "session.step must call advance_day"
    assert seen[-1] == "F1s", (
        f"EngineSession must forward applied obs_scenario into advance_day; "
        f"got {seen[-1]!r}"
    )


# ---------------------------------------------------------------------------
# AC: SCN-P2 stays Out (guards)
# ---------------------------------------------------------------------------


def test_scenario_id_literal_excludes_p2() -> None:
    args = get_args(ScenarioId)
    assert args == _LADDER or set(args) == set(_LADDER)
    assert "P2" not in args


def test_mask_for_rejects_p2() -> None:
    with pytest.raises((KeyError, ValueError, TypeError)):
        mask_for("P2")


def test_scn_p2_backlog_and_adr_remain_out() -> None:
    backlog = _BACKLOG.read_text(encoding="utf-8")
    assert "SCN-P2" in backlog
    assert "do not reopen" in backlog.lower() or "Do not reopen" in backlog
    adr = _ADR_0022.read_text(encoding="utf-8")
    assert "SCN-P2" in adr
    # Must not reopen as a studio rung — ADR status stays accepted Out.
    assert "STATUS:" in adr


def test_filter_types_scenario_present_has_no_p2_key() -> None:
    src = _TYPES_SRC.read_text(encoding="utf-8")
    # Soft guard: _SCENARIO_PRESENT must not map "P2".
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == "P2":
                    pytest.fail("_SCENARIO_PRESENT must not include P2")

"""T-113 RED: lazy per-rung obs_scenario caches + EngineSession.set_obs_scenario.

Locks `.team/specs/T-113.md` and ADR 0123. Catch-up must replay the richest log
into a new RBPF; naive in-place particle retarget stays forbidden.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.filter.rbpf import RBPF
from blueberries_voi.filter.types import mask_for
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator.session import EngineSession

_REPO = Path(__file__).resolve().parents[1]
_SESSION_SRC = _REPO / "src" / "blueberries_voi" / "simulator" / "session.py"
_RPC_SRC = _REPO / "packaging" / "pyodide" / "session_rpc.py"
_WORKER_SRC = _REPO / "packaging" / "pyodide" / "worker.js"
_API_PKG = "blueberries_voi.api"


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T113-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="T113-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "shipments": _fixture_shipments(),
        "n_particles": 16,
        "H": 2,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
        "obs_scenario": "P1",
    }
    cfg.update(overrides)
    return cfg


def _day_field(day: Any, name: str) -> Any:
    if isinstance(day, dict):
        return day.get(name)
    return getattr(day, name, None)


def _richest_log(session: EngineSession) -> list[Any]:
    for attr in ("_richest_log", "_episode_log", "_obs_log"):
        raw = getattr(session, attr, None)
        if raw is None:
            continue
        days = getattr(raw, "days", raw)
        if isinstance(days, list):
            return days
    pytest.fail(
        "EngineSession must persist a richest episode log "
        "(_richest_log / _episode_log) including lot maps and receipt meta; "
        "thin Snapshot history is not enough"
    )


def _assert_snapshot(payload: Any) -> dict[str, Any]:
    assert isinstance(payload, dict), f"expected Snapshot dict, got {type(payload)!r}"
    assert "belief" in payload
    assert "applied_config" in payload
    applied = payload["applied_config"]
    assert isinstance(applied, dict)
    return payload


def _set_obs(session: EngineSession, obs_scenario: str) -> Any:
    fn = getattr(session, "set_obs_scenario", None)
    assert callable(fn), "EngineSession.set_obs_scenario is required (T-113 / ADR 0123)"
    return fn(obs_scenario)


# ---------------------------------------------------------------------------
# AC: richest episode log after advance_day / EngineSession.step
# ---------------------------------------------------------------------------


def test_session_keeps_richest_log_fields_after_steps() -> None:
    session = EngineSession()
    session.init(_config(), seed=11)
    for _ in range(8):
        session.step(24)
    log = _richest_log(session)
    assert len(log) == 8
    names = ("sales_by_lot", "waste_by_lot", "age_at_receipt", "pack_date")
    seen = {n: False for n in names}
    for day in log:
        for name in names:
            val = _day_field(day, name)
            if val is None:
                continue
            if name in {"sales_by_lot", "waste_by_lot"}:
                assert isinstance(val, dict)
                seen[name] = True
            elif name == "age_at_receipt":
                assert isinstance(val, (int, float, np.floating))
                seen[name] = True
            elif name == "pack_date":
                assert isinstance(val, (date, str))
                seen[name] = True
    missing = [n for n, ok in seen.items() if not ok]
    assert not missing, (
        f"richest log never stored {missing} across 8 days "
        "(fields must persist when they exist for the day)"
    )


def test_snapshot_history_may_stay_thin_while_richest_log_is_separate() -> None:
    session = EngineSession()
    session.init(_config(), seed=3)
    session.step(16)
    history = session._snapshot()["history"]
    assert isinstance(history, list) and history
    log = _richest_log(session)
    assert len(log) >= len(history)
    rich_day = log[0]
    assert _day_field(rich_day, "sales_total") is not None
    assert _day_field(rich_day, "waste_total") is not None


# ---------------------------------------------------------------------------
# AC: set_obs_scenario catch-up protocol
# ---------------------------------------------------------------------------


def test_set_obs_scenario_exists_and_returns_snapshot_without_reset() -> None:
    assert hasattr(EngineSession, "set_obs_scenario"), (
        "EngineSession.set_obs_scenario is required (T-113 / ADR 0123)"
    )
    session = EngineSession()
    session.init(_config(obs_scenario="P1"), seed=5)
    session.step(16)
    session.step(16)
    before_day = int(session._snapshot()["episode_day"])
    before_seq = int(session._snapshot()["seq"])
    snap = _set_obs(session, "F2")
    payload = _assert_snapshot(snap)
    assert payload["applied_config"]["obs_scenario"] == "F2"
    assert int(payload["episode_day"]) == before_day
    assert int(payload["seq"]) == before_seq


def test_first_select_catchup_steps_days_0_through_t_minus_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stepped: list[int] = []
    real = RBPF.step

    def _spy(self: RBPF, obs: Any, rng: Any = None) -> Any:
        stepped.append(int(self._day))
        return real(self, obs, rng)

    monkeypatch.setattr(RBPF, "step", _spy)
    session = EngineSession()
    session.init(_config(obs_scenario="P1"), seed=9)
    t = 4
    for _ in range(t):
        session.step(24)
    stepped.clear()
    _set_obs(session, "F1")
    assert stepped == list(range(t)), (
        f"first select at day {t} must initialize a new RBPF and step 0…{t - 1}; "
        f"got days {stepped!r}"
    )


def test_switch_back_catchup_steps_only_the_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = EngineSession()
    session.init(_config(obs_scenario="P1"), seed=13)
    for _ in range(3):
        session.step(24)
    _set_obs(session, "F2")
    _set_obs(session, "P1")
    for _ in range(2):
        session.step(16)

    stepped: list[int] = []
    real = RBPF.step

    def _spy(self: RBPF, obs: Any, rng: Any = None) -> Any:
        stepped.append(int(self._day))
        return real(self, obs, rng)

    monkeypatch.setattr(RBPF, "step", _spy)
    _set_obs(session, "F2")
    assert stepped == [3, 4], (
        "switch-back must step only last_synced+1 … now (days 3,4 after "
        f"warming F2 at t=3 then advancing 2 on P1); got {stepped!r}"
    )


@pytest.mark.parametrize("bad_id", ["P2", "B-state", "not-a-scenario", ""])
def test_set_obs_scenario_invalid_id_raises_like_mask_for(bad_id: str) -> None:
    session = EngineSession()
    session.init(_config(), seed=1)
    with pytest.raises((ValueError, KeyError, TypeError)):
        mask_for(bad_id)
    fn = getattr(session, "set_obs_scenario", None)
    assert callable(fn), "EngineSession.set_obs_scenario is required (T-113 / ADR 0123)"
    with pytest.raises((ValueError, KeyError, TypeError)):
        fn(bad_id)


# ---------------------------------------------------------------------------
# AC: CRN golden — catch-up matches never-switched filter
# ---------------------------------------------------------------------------


def _belief_vec(snap: dict[str, Any]) -> np.ndarray:
    bel = snap["belief"]
    return np.asarray(bel["age_marginals"], dtype=float)


def test_catchup_matches_never_switched_filter_crn() -> None:
    seed = 42
    days = 5
    live = EngineSession()
    live.init(_config(obs_scenario="F2"), seed=seed)
    for _ in range(days):
        live.step(24)
    live_snap = live._snapshot()

    switched = EngineSession()
    switched.init(_config(obs_scenario="P1"), seed=seed)
    for _ in range(days):
        switched.step(24)
    caught = _set_obs(switched, "F2")
    payload = _assert_snapshot(caught)
    np.testing.assert_allclose(
        _belief_vec(payload),
        _belief_vec(live_snap),
        rtol=0.0,
        atol=0.0,
        err_msg="catch-up F2 must match a filter that was F2 the whole episode (CRN)",
    )
    np.testing.assert_allclose(
        np.asarray(payload["belief"]["lot_counts"], dtype=float),
        np.asarray(live_snap["belief"]["lot_counts"], dtype=float),
        rtol=0.0,
        atol=0.0,
    )


# ---------------------------------------------------------------------------
# AC: advance/act step only the active filter; Reset wipes caches
# ---------------------------------------------------------------------------


def test_step_and_act_advance_only_the_active_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = EngineSession()
    session.init(_config(obs_scenario="P1"), seed=17)
    for _ in range(3):
        session.step(24)
    _set_obs(session, "F2")
    _set_obs(session, "P1")

    owners: list[int] = []
    real = RBPF.step

    def _spy(self: RBPF, obs: Any, rng: Any = None) -> Any:
        owners.append(id(self))
        return real(self, obs, rng)

    monkeypatch.setattr(RBPF, "step", _spy)
    active = session._state.rbpf
    assert active is not None
    session.step(16)
    session.act(policy="constant", order_qty=8)
    assert owners, "step/act must call RBPF.step on the active filter"
    assert all(oid == id(active) for oid in owners), (
        "advance_day / act must step only the active filter; warmed rungs stay behind"
    )


def test_reset_wipes_richest_log_and_per_rung_caches() -> None:
    session = EngineSession()
    session.init(_config(obs_scenario="P1"), seed=19)
    for _ in range(4):
        session.step(24)
    _set_obs(session, "F1")
    assert len(_richest_log(session)) == 4
    rbpf_before = session._state.rbpf
    session.reset(_config(obs_scenario="P1"), seed=19)
    log = _richest_log(session)
    assert log == [], "Reset must wipe the richest episode log"
    assert session._state.rbpf is not rbpf_before
    snap = _set_obs(session, "F2")
    _assert_snapshot(snap)
    assert int(snap["episode_day"]) == 0
    assert len(_richest_log(session)) == 0


def test_init_wipes_caches_like_reset() -> None:
    session = EngineSession()
    session.init(_config(), seed=2)
    session.step(16)
    _set_obs(session, "F2")
    session.init(_config(), seed=2)
    assert _richest_log(session) == []


# ---------------------------------------------------------------------------
# AC: no in-place particle retarget
# ---------------------------------------------------------------------------


def test_set_obs_scenario_creates_a_distinct_rbpf_not_in_place_weights() -> None:
    session = EngineSession()
    session.init(_config(obs_scenario="P1"), seed=23)
    for _ in range(3):
        session.step(24)
    live = session._state.rbpf
    assert live is not None
    live_id = id(live)
    state_id = id(live._state)
    _set_obs(session, "F2")
    new = session._state.rbpf
    assert new is not None
    assert id(new) != live_id, "catch-up must construct a distinct RBPF"
    assert id(new._state) != state_id, (
        "must not mutate the live particle cloud in place"
    )


def test_session_source_does_not_retarget_particle_obs_scenario_in_place() -> None:
    src = _SESSION_SRC.read_text(encoding="utf-8")
    assert "set_obs_scenario" in src
    forbidden = (
        "._obs_scenario =",
        "particle._obs_scenario",
        "p._obs_scenario",
    )
    # Live cloud field retarget without replay is the forbidden path.
    assert "weights" not in src.split("def set_obs_scenario", 1)[-1][:800] or (
        "RBPF(" in src.split("def set_obs_scenario", 1)[-1]
    )
    assert "particle._obs_scenario" not in src
    for needle in forbidden[1:]:
        assert needle not in src


# ---------------------------------------------------------------------------
# AC: session_rpc + FastAPI forward set_obs_scenario
# ---------------------------------------------------------------------------


def test_session_rpc_dispatches_set_obs_scenario() -> None:
    spec = importlib.util.spec_from_file_location(
        "t113_session_rpc",
        _RPC_SRC,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    methods = getattr(mod, "_RPC_METHODS", None)
    assert methods is not None and "set_obs_scenario" in methods
    init = json.loads(
        mod.handle_rpc(
            {
                "id": "1",
                "method": "init",
                "params": {"config": _config(), "seed": 4},
            }
        )
    )
    assert init.get("ok") is True
    json.loads(
        mod.handle_rpc({"id": "2", "method": "step", "params": {"order_qty": 16}})
    )
    resp = json.loads(
        mod.handle_rpc(
            {
                "id": "3",
                "method": "set_obs_scenario",
                "params": {"obs_scenario": "F1"},
            }
        )
    )
    assert resp.get("ok") is True, f"RPC set_obs_scenario failed: {resp!r}"
    result = resp["result"]
    assert isinstance(result, dict)
    assert result["applied_config"]["obs_scenario"] == "F1"


def test_pyodide_worker_mentions_set_obs_scenario() -> None:
    text = _WORKER_SRC.read_text(encoding="utf-8")
    assert "set_obs_scenario" in text


def _asgi_client() -> Any:
    app = importlib.import_module(_API_PKG).app
    from starlette.testclient import TestClient

    return TestClient(app)


def test_fastapi_forwards_set_obs_scenario_on_session_object() -> None:
    client = _asgi_client()
    created = client.post("/sessions")
    assert created.status_code == 200
    sid = created.json()["session_id"]
    cfg = _config()
    cfg["shipments"] = [
        {
            "shipment_id": s.shipment_id,
            "times_d": s.times_d.tolist(),
            "temps_c": s.temps_c.tolist(),
            "duration_d": s.duration_d,
        }
        for s in cfg["shipments"]
    ]
    init_resp = client.post(
        f"/sessions/{sid}/init",
        json={"config": cfg, "seed": 8},
    )
    assert init_resp.status_code == 200
    assert (
        client.post(f"/sessions/{sid}/step", json={"order_qty": 16}).status_code == 200
    )
    resp = client.post(
        f"/sessions/{sid}/set_obs_scenario",
        json={"obs_scenario": "F2"},
    )
    assert resp.status_code == 200, (
        f"POST /sessions/{{id}}/set_obs_scenario must exist on the session object; "
        f"got {resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert body["applied_config"]["obs_scenario"] == "F2"

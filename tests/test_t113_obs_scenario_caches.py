"""T-125 migrated T-113: EngineSession.set_obs_scenario (PyO3) + WASM worker dispatch.

Locks `.team/specs/T-125.md` AC-mixed: catch-up via Rust ``PyEngineSession`` and
``packaging/wasm/worker.js`` — no FastAPI or ``packaging/pyodide/session_rpc.py``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from blueberries_voi.filter.types import mask_for
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator.belief import empty_flat_belief
from blueberries_voi.simulator.session import EngineSession

_REPO = Path(__file__).resolve().parents[1]
_WASM_WORKER = _REPO / "packaging" / "wasm" / "worker.js"
_PYODIDE_RPC = _REPO / "packaging" / "pyodide" / "session_rpc.py"
_API_PKG = "blueberries_voi.api"

_FLAT = empty_flat_belief(L=2, K=4)


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


def _snap(*, seq: int = 0, day: int = 0, obs: str = "P1") -> dict[str, Any]:
    return {
        "seq": seq,
        "episode_day": day,
        "belief": dict(_FLAT),
        "applied_config": {"obs_scenario": obs},
        "history": [],
        "live_lots": [],
        "pipeline": [],
    }


class _FakePyEngineSession:
    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)
        self.obs_scenario = "P1"
        self.set_obs_calls: list[str] = []

    def init(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return _snap(obs=self.obs_scenario)

    def step(self, order_qty: int) -> dict[str, Any]:
        return {
            "seq": 1,
            "episode_day": 0,
            "day": {"day": 0, "order_qty": order_qty},
            "belief": dict(_FLAT),
            "live_lots": [],
            "pipeline": [],
            "drop_oldest": False,
        }

    def set_obs_scenario(self, obs_scenario: str) -> dict[str, Any]:
        self.set_obs_calls.append(str(obs_scenario))
        self.obs_scenario = str(obs_scenario)
        return _snap(obs=self.obs_scenario)


def _install_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, _FakePyEngineSession]:
    holder: dict[str, _FakePyEngineSession] = {}

    def factory(seed: int = 0) -> _FakePyEngineSession:
        sess = _FakePyEngineSession(seed)
        holder["s"] = sess
        return sess

    fake = SimpleNamespace(PyEngineSession=factory)
    monkeypatch.setattr("blueberries_voi.backend.rust_available", lambda: True)
    monkeypatch.setattr("blueberries_voi.backend.rust_core", fake)
    return holder


def _wasm_worker_source() -> str:
    assert _WASM_WORKER.is_file(), "packaging/wasm/worker.js must exist (T-125)"
    return _WASM_WORKER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-mixed: EngineSession.set_obs_scenario (PyO3 dispatch)
# ---------------------------------------------------------------------------


def test_set_obs_scenario_exists_and_returns_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert hasattr(EngineSession, "set_obs_scenario")
    holder = _install_fake(monkeypatch)
    session = EngineSession()
    session.init(_config(obs_scenario="P1"), seed=5)
    snap = session.set_obs_scenario("F2")
    assert isinstance(snap, dict)
    assert snap["applied_config"]["obs_scenario"] == "F2"
    inner = holder["s"]
    assert inner.set_obs_calls == ["F2"]


def test_set_obs_scenario_delegates_to_pyo3_rust_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = _install_fake(monkeypatch)
    session = EngineSession()
    session.init(_config(), seed=1)
    session.set_obs_scenario("F1")
    assert holder["s"].set_obs_calls == ["F1"]


@pytest.mark.parametrize("bad_id", ["P2", "B-state", "not-a-scenario", ""])
def test_set_obs_scenario_invalid_id_raises_like_mask_for(
    bad_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = _install_fake(monkeypatch)
    session = EngineSession()
    session.init(_config(), seed=1)
    with pytest.raises((ValueError, KeyError, TypeError)):
        mask_for(bad_id)
    with pytest.raises((ValueError, KeyError, TypeError)):
        session.set_obs_scenario(bad_id)
    assert holder["s"].set_obs_calls == []


# ---------------------------------------------------------------------------
# AC-mixed: WASM worker dispatches set_obs_scenario
# ---------------------------------------------------------------------------


def test_wasm_worker_mentions_set_obs_scenario() -> None:
    text = _wasm_worker_source()
    assert "set_obs_scenario" in text, (
        "wasm worker.js must mention set_obs_scenario in RPC dispatch (T-113 / T-125)"
    )


def test_wasm_worker_rpc_surface_matches_session_contract() -> None:
    text = _wasm_worker_source()
    for method in ("init", "step", "act", "set_obs_scenario"):
        assert method in text, f"wasm worker must support RPC method {method!r}"


# ---------------------------------------------------------------------------
# AC-pyodide / AC-api: retired FastAPI + session_rpc paths absent (T-125)
# ---------------------------------------------------------------------------


def test_packaging_pyodide_session_rpc_absent() -> None:
    assert not _PYODIDE_RPC.is_file(), (
        "packaging/pyodide/session_rpc.py must be deleted (T-125); "
        "set_obs_scenario is wasm + PyO3 only"
    )


def test_fastapi_api_package_absent() -> None:
    api_dir = _REPO / "src" / "blueberries_voi" / "api"
    assert not api_dir.is_dir(), (
        "src/blueberries_voi/api/ must be deleted (T-125 AC-api); "
        "no FastAPI set_obs_scenario forwarding"
    )


def test_blueberries_voi_api_not_importable() -> None:
    import importlib.util

    spec = importlib.util.find_spec(_API_PKG)
    assert spec is None, (
        f"{_API_PKG} must not be importable after T-125 AC-api retirement"
    )

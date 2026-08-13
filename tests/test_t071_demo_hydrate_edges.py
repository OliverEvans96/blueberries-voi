"""T-071 demo hydrate at FastAPI + Pyodide RPC edges (RED).

Locks ``.team/specs/T-071.md`` and ADR 0107: missing/empty ``shipments`` on
init/reset are filled with a parquet-free demo fixture at the **host edges
only**; ``EngineSession`` stays strict; non-empty client shipments are kept.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator.schema import validate_snapshot
from blueberries_voi.simulator.session import EngineSession

_REPO_ROOT = Path(__file__).resolve().parents[1]
_API_PKG = "blueberries_voi.api"

_INIT = "/sessions/{session_id}/init"
_RESET = "/sessions/{session_id}/reset"
_SESSION_CREATE = "/sessions"

_RPC_PATH = _REPO_ROOT / "packaging" / "pyodide" / "session_rpc.py"
_WORKER_PATH = _REPO_ROOT / "packaging" / "pyodide" / "worker.js"

_CLIENT_SHIPMENT_ID = "T071-CLIENT-KEEP"


# ---------------------------------------------------------------------------
# Shared helpers (mirror T-050 / T-047 styles)
# ---------------------------------------------------------------------------


def _json_shipments(*, shipment_id: str = _CLIENT_SHIPMENT_ID) -> list[dict[str, Any]]:
    return [
        {
            "shipment_id": shipment_id,
            "times_d": [0.0, 1.0, 2.0],
            "temps_c": [1.0, 1.0, 1.0],
            "duration_d": 2.0,
        }
    ]


def _resolve_app() -> Any:
    try:
        mod = importlib.import_module(_API_PKG)
    except ImportError as exc:
        pytest.fail(
            f"{_API_PKG} must be importable; got {exc!r}",
            pytrace=False,
        )
    app = getattr(mod, "app", None)
    if app is None:
        pytest.fail(f"{_API_PKG}.app must export the ASGI application", pytrace=False)
    return app


def _asgi_client(app: Any) -> Any:
    try:
        from starlette.testclient import TestClient

        return TestClient(app)
    except ImportError:
        pass
    try:
        from fastapi.testclient import TestClient

        return TestClient(app)
    except ImportError:
        pass
    pytest.fail(
        "T-071 requires Starlette/FastAPI TestClient ([api] extra)",
        pytrace=False,
    )


def _response_json(resp: Any) -> Any:
    if hasattr(resp, "json") and callable(resp.json):
        data = resp.json()
        return data() if callable(data) else data
    body = getattr(resp, "content", None) or getattr(resp, "text", b"")
    if isinstance(body, bytes):
        return json.loads(body.decode("utf-8"))
    if isinstance(body, (str, bytearray)):
        return json.loads(body)
    pytest.fail(f"response body is not JSON-decodable: {type(body)!r}")


def _status(resp: Any) -> int:
    return int(resp.status_code)


def _create_session(client: Any) -> str:
    resp = client.post(_SESSION_CREATE)
    assert _status(resp) in {200, 201}, (
        f"POST {_SESSION_CREATE} must create a session; got {_status(resp)}"
    )
    payload = _response_json(resp)
    assert isinstance(payload, Mapping)
    sid = payload.get("session_id")
    assert isinstance(sid, str) and sid
    return sid


def _path(template: str, session_id: str) -> str:
    return template.format(session_id=session_id)


def _shipment_ids(ships: Any) -> list[str]:
    if not isinstance(ships, Sequence) or isinstance(ships, (str, bytes)):
        return []
    out: list[str] = []
    for item in ships:
        if isinstance(item, ShipmentTrace):
            out.append(str(item.shipment_id))
        elif isinstance(item, Mapping):
            out.append(str(item.get("shipment_id", "")))
    return out


def _ban_abdella_parquet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail if any edge tries to load Abdella parquet (ADR 0107)."""

    def _boom(*_a: Any, **_k: Any) -> list[ShipmentTrace]:
        raise AssertionError(
            "demo hydrate must be parquet-free (smoke_cool_shipments); "
            "must not call load_abdella_shipments / require data/abdella"
        )

    import blueberries_voi.model.abdella as abdella
    import blueberries_voi.sim.shipments as shipments_mod

    monkeypatch.setattr(abdella, "load_abdella_shipments", _boom)
    if hasattr(shipments_mod, "load_abdella_shipments"):
        monkeypatch.setattr(shipments_mod, "load_abdella_shipments", _boom)
    if hasattr(shipments_mod, "default_shipments"):
        monkeypatch.setattr(shipments_mod, "default_shipments", _boom)


def _load_rpc_module() -> Any:
    rel = _RPC_PATH.relative_to(_REPO_ROOT).as_posix()
    assert _RPC_PATH.is_file(), f"missing {rel}"
    name = f"_t071_session_rpc_{id(object())}"
    spec = importlib.util.spec_from_file_location(name, _RPC_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load RPC module from {_RPC_PATH}", pytrace=False)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _rpc_handle(mod: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    fn = getattr(mod, "handle_rpc", None)
    assert callable(fn), "session_rpc.py must export handle_rpc"
    raw = fn(dict(request))
    if isinstance(raw, str):
        decoded = json.loads(raw)
    elif isinstance(raw, Mapping):
        decoded = json.loads(json.dumps(raw))
    else:
        pytest.fail(f"handle_rpc must return JSON string or mapping; got {type(raw)!r}")
    assert isinstance(decoded, dict)
    return decoded


def _assert_rpc_ok(resp: Mapping[str, Any], *, req_id: str) -> Any:
    assert resp.get("id") == req_id
    assert resp.get("ok") is True, (
        f"RPC must succeed with demo hydrate; got error={resp.get('error')!r}"
    )
    assert "result" in resp
    return resp["result"]


# ---------------------------------------------------------------------------
# AC: FastAPI init without / empty shipments → 200 Snapshot (not 422)
# ---------------------------------------------------------------------------


def test_api_init_without_shipments_returns_200_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ban_abdella_parquet(monkeypatch)
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    resp = client.post(
        _path(_INIT, sid),
        json={"config": {"n_particles": 32, "H": 3, "L": 2, "K": 4}, "seed": 7},
    )
    assert _status(resp) == 200, (
        "init without shipments must demo-hydrate and return 200 Snapshot "
        f"(not 422); got {_status(resp)} body={_response_json(resp)!r}"
    )
    snap = _response_json(resp)
    assert isinstance(snap, Mapping)
    validate_snapshot(snap)


def test_api_init_with_empty_shipments_returns_200_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ban_abdella_parquet(monkeypatch)
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    resp = client.post(
        _path(_INIT, sid),
        json={
            "config": {"shipments": [], "n_particles": 32, "H": 3, "L": 2, "K": 4},
            "seed": 11,
        },
    )
    assert _status(resp) == 200, (
        "init with empty shipments must demo-hydrate and return 200; "
        f"got {_status(resp)} body={_response_json(resp)!r}"
    )
    validate_snapshot(_response_json(resp))


# ---------------------------------------------------------------------------
# AC: FastAPI reset without / empty shipments → 200 Snapshot
# ---------------------------------------------------------------------------


def test_api_reset_with_empty_shipments_returns_200_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ban_abdella_parquet(monkeypatch)
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    # Seed the session with explicit client shipments so reset hydrate is isolated.
    primed = client.post(
        _path(_INIT, sid),
        json={
            "config": {
                "shipments": _json_shipments(),
                "n_particles": 32,
                "H": 3,
                "L": 2,
                "K": 4,
            },
            "seed": 3,
        },
    )
    assert _status(primed) == 200, f"prime init failed: {_response_json(primed)!r}"

    resp = client.post(
        _path(_RESET, sid),
        json={
            "config": {"shipments": [], "n_particles": 32, "H": 3, "L": 2, "K": 4},
            "seed": 5,
        },
    )
    assert _status(resp) == 200, (
        "reset with empty shipments must demo-hydrate and return 200 Snapshot; "
        f"got {_status(resp)} body={_response_json(resp)!r}"
    )
    validate_snapshot(_response_json(resp))


def test_api_reset_without_shipments_key_returns_200_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ban_abdella_parquet(monkeypatch)
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    primed = client.post(
        _path(_INIT, sid),
        json={
            "config": {
                "shipments": _json_shipments(),
                "n_particles": 32,
                "H": 3,
                "L": 2,
                "K": 4,
            },
            "seed": 3,
        },
    )
    assert _status(primed) == 200

    resp = client.post(
        _path(_RESET, sid),
        json={"config": {"n_particles": 32, "H": 3, "L": 2, "K": 4}, "seed": 9},
    )
    assert _status(resp) == 200, (
        "reset without shipments key must demo-hydrate and return 200; "
        f"got {_status(resp)} body={_response_json(resp)!r}"
    )
    validate_snapshot(_response_json(resp))


# ---------------------------------------------------------------------------
# AC: non-empty client shipments preserved (not overwritten)
# ---------------------------------------------------------------------------


def test_api_init_preserves_nonempty_client_shipments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[Any] = []
    real_init = EngineSession.init

    def _spy(
        self: EngineSession,
        config: Mapping[str, Any],
        *,
        seed: int | None = None,
    ) -> Any:
        captured.append(config.get("shipments"))
        return real_init(self, config, seed=seed)

    monkeypatch.setattr(EngineSession, "init", _spy)
    # Also patch the name bound inside the API module if already imported.
    try:
        api_app = importlib.import_module("blueberries_voi.api.app")
        monkeypatch.setattr(api_app.EngineSession, "init", _spy)
    except ImportError:
        pass

    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    client_ships = _json_shipments(shipment_id=_CLIENT_SHIPMENT_ID)
    resp = client.post(
        _path(_INIT, sid),
        json={
            "config": {
                "shipments": client_ships,
                "n_particles": 32,
                "H": 3,
                "L": 2,
                "K": 4,
            },
            "seed": 13,
        },
    )
    assert _status(resp) == 200, (
        f"init with client shipments must succeed; got {_status(resp)} "
        f"{_response_json(resp)!r}"
    )
    assert captured, "EngineSession.init must be called"
    ids = _shipment_ids(captured[-1])
    assert ids == [_CLIENT_SHIPMENT_ID], (
        "non-empty client shipments must not be overwritten by demo hydrate; "
        f"got ids={ids!r}"
    )


def test_api_reset_preserves_nonempty_client_shipments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[Any] = []
    real_init = EngineSession.init

    def _spy(
        self: EngineSession,
        config: Mapping[str, Any],
        *,
        seed: int | None = None,
    ) -> Any:
        captured.append(config.get("shipments"))
        return real_init(self, config, seed=seed)

    monkeypatch.setattr(EngineSession, "init", _spy)
    try:
        api_app = importlib.import_module("blueberries_voi.api.app")
        monkeypatch.setattr(api_app.EngineSession, "init", _spy)
    except ImportError:
        pass

    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    prime_ships = _json_shipments(shipment_id="T071-PRIME")
    assert (
        _status(
            client.post(
                _path(_INIT, sid),
                json={
                    "config": {
                        "shipments": prime_ships,
                        "n_particles": 32,
                        "H": 3,
                        "L": 2,
                        "K": 4,
                    },
                    "seed": 1,
                },
            )
        )
        == 200
    )
    captured.clear()

    keep_id = "T071-RESET-KEEP"
    resp = client.post(
        _path(_RESET, sid),
        json={
            "config": {
                "shipments": _json_shipments(shipment_id=keep_id),
                "n_particles": 32,
                "H": 3,
                "L": 2,
                "K": 4,
            },
            "seed": 2,
        },
    )
    assert _status(resp) == 200
    assert captured, "reset must call EngineSession.init with config"
    ids = _shipment_ids(captured[-1])
    assert ids == [keep_id], f"reset must preserve client shipments; got ids={ids!r}"


# ---------------------------------------------------------------------------
# AC: session_rpc hydrates missing/empty shipments on init / reset
# ---------------------------------------------------------------------------


def test_rpc_init_without_shipments_returns_ok_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ban_abdella_parquet(monkeypatch)
    mod = _load_rpc_module()
    resp = _rpc_handle(
        mod,
        {
            "id": "t071-init-missing",
            "method": "init",
            "params": {
                "config": {"n_particles": 32, "H": 3, "L": 2, "K": 4},
                "seed": 47,
            },
        },
    )
    snap = _assert_rpc_ok(resp, req_id="t071-init-missing")
    assert isinstance(snap, Mapping)
    validate_snapshot(snap)


def test_rpc_init_with_empty_shipments_returns_ok_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ban_abdella_parquet(monkeypatch)
    mod = _load_rpc_module()
    resp = _rpc_handle(
        mod,
        {
            "id": "t071-init-empty",
            "method": "init",
            "params": {
                "config": {
                    "shipments": [],
                    "n_particles": 32,
                    "H": 3,
                    "L": 2,
                    "K": 4,
                },
                "seed": 47,
            },
        },
    )
    snap = _assert_rpc_ok(resp, req_id="t071-init-empty")
    validate_snapshot(snap)


def test_rpc_reset_with_empty_shipments_returns_ok_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ban_abdella_parquet(monkeypatch)
    mod = _load_rpc_module()
    # Prime with explicit traces so reset hydrate is the behaviour under test.
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    prime = [
        ShipmentTrace(
            shipment_id="T071-RPC-PRIME",
            times_d=times,
            temps_c=np.asarray([1.0, 1.0, 1.0], dtype=float),
            duration_d=2.0,
        )
    ]
    prepare = getattr(mod, "prepare_demo_config", None)
    cfg: dict[str, Any] = {"n_particles": 32, "H": 3, "L": 2, "K": 4}
    if callable(prepare):
        cfg = prepare(cfg, shipments=prime)
    else:
        cfg = {**cfg, "shipments": prime}
    primed = _rpc_handle(
        mod,
        {
            "id": "t071-rpc-prime",
            "method": "init",
            "params": {"config": cfg, "seed": 1},
        },
    )
    _assert_rpc_ok(primed, req_id="t071-rpc-prime")

    resp = _rpc_handle(
        mod,
        {
            "id": "t071-rpc-reset-empty",
            "method": "reset",
            "params": {
                "config": {"shipments": [], "n_particles": 32, "H": 3, "L": 2, "K": 4},
                "seed": 2,
            },
        },
    )
    snap = _assert_rpc_ok(resp, req_id="t071-rpc-reset-empty")
    validate_snapshot(snap)


def test_rpc_preserves_nonempty_client_shipments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_rpc_module()
    captured: list[Any] = []
    real_init = EngineSession.init

    def _spy(
        self: EngineSession,
        config: Mapping[str, Any],
        *,
        seed: int | None = None,
    ) -> Any:
        captured.append(config.get("shipments"))
        return real_init(self, config, seed=seed)

    monkeypatch.setattr(EngineSession, "init", _spy)
    if hasattr(mod, "EngineSession"):
        monkeypatch.setattr(mod.EngineSession, "init", _spy)

    keep = [
        ShipmentTrace(
            shipment_id=_CLIENT_SHIPMENT_ID,
            times_d=np.asarray([0.0, 1.0, 2.0], dtype=float),
            temps_c=np.asarray([1.0, 1.0, 1.0], dtype=float),
            duration_d=2.0,
        )
    ]
    prepare = getattr(mod, "prepare_demo_config", None)
    cfg: dict[str, Any] = {"n_particles": 32, "H": 3, "L": 2, "K": 4}
    if callable(prepare):
        # Even if prepare is used, non-empty client shipments must win.
        cfg = prepare(dict(cfg), shipments=keep)
    else:
        cfg = {**cfg, "shipments": keep}

    resp = _rpc_handle(
        mod,
        {
            "id": "t071-rpc-keep",
            "method": "init",
            "params": {"config": cfg, "seed": 7},
        },
    )
    _assert_rpc_ok(resp, req_id="t071-rpc-keep")
    assert captured, "EngineSession.init must be called"
    ids = _shipment_ids(captured[-1])
    assert ids == [_CLIENT_SHIPMENT_ID], (
        f"RPC must preserve non-empty client shipments; got {ids!r}"
    )


def test_worker_js_dispatch_mentions_demo_hydrate_source() -> None:
    """Worker inline Python must mirror session_rpc demo hydrate (ADR 0107)."""
    assert _WORKER_PATH.is_file(), "packaging/pyodide/worker.js must exist"
    text = _WORKER_PATH.read_text(encoding="utf-8")
    has_fixture = (
        "smoke_cool_shipments" in text
        or "ensure_demo_shipments" in text
        or "prepare_demo_config" in text
    )
    assert has_fixture, (
        "worker.js dispatch must hydrate demo shipments the same way as "
        "session_rpc (smoke_cool_shipments / ensure_demo_shipments / "
        "prepare_demo_config); currently forwards empty config to EngineSession"
    )


# ---------------------------------------------------------------------------
# AC: EngineSession stays strict (no Abdella / demo default inside session)
# ---------------------------------------------------------------------------


def test_engine_session_init_without_shipments_still_raises_value_error() -> None:
    with pytest.raises(ValueError, match=r"shipments"):
        EngineSession().init({})


def test_engine_session_init_with_empty_shipments_still_raises_value_error() -> None:
    with pytest.raises(ValueError, match=r"shipments"):
        EngineSession().init({"shipments": []})


# ---------------------------------------------------------------------------
# AC: hydrate is parquet-free (no data/abdella required)
# ---------------------------------------------------------------------------


def test_demo_hydrate_edges_do_not_require_data_abdella(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """API + RPC hydrate must work with data/abdella absent / unloadable."""
    _ban_abdella_parquet(monkeypatch)
    # Point any Path-based default away from a real tree if code looks it up.
    fake_data = tmp_path / "no-abdella-here"
    fake_data.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))

    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    api_resp = client.post(
        _path(_INIT, sid),
        json={"config": {}, "seed": 21},
    )
    assert _status(api_resp) == 200, (
        "API demo hydrate must not require data/abdella; "
        f"got {_status(api_resp)} {_response_json(api_resp)!r}"
    )
    validate_snapshot(_response_json(api_resp))

    mod = _load_rpc_module()
    rpc_resp = _rpc_handle(
        mod,
        {
            "id": "t071-no-parquet",
            "method": "init",
            "params": {"config": {}, "seed": 22},
        },
    )
    snap = _assert_rpc_ok(rpc_resp, req_id="t071-no-parquet")
    validate_snapshot(snap)

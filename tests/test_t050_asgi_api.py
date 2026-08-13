"""T-050 ASGI app wrapping EngineSession — RED contracts.

Locks ``.team/specs/T-050.md``, ADR 0100 (ASGI sessions), T-049 route table,
and ADR 0098 Snapshot / DayDelta wire (validators from T-045).

No production ``api/`` module in this worktree — tests must fail for missing
behaviour / packaging, not import typos in this file.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from blueberries_voi.simulator.schema import (
    validate_day_delta,
    validate_snapshot,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src" / "blueberries_voi"
_API_PKG = "blueberries_voi.api"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "economics",
        "pnl_series",
        "pnl_totals",
        "ghost",
        "ghost_deltas",
        "heatmap",
        "density",
        "ViewModel",
        "view_model",
    }
)
_FORBIDDEN_IMPORT_ROOTS = frozenset({"matplotlib", "pyplot"})

# T-049 Interfaces
_SESSION_CREATE = "/sessions"
_SESSION_PATH = "/sessions/{session_id}"
_INIT = "/sessions/{session_id}/init"
_STEP = "/sessions/{session_id}/step"
_STEP_N = "/sessions/{session_id}/step_n"
_RESET = "/sessions/{session_id}/reset"
_ACT = "/sessions/{session_id}/act"


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _load_pyproject() -> dict[str, Any]:
    assert _PYPROJECT.is_file(), "pyproject.toml missing"
    with _PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    assert isinstance(data, dict)
    return data


def _json_shipments() -> list[dict[str, Any]]:
    """JSON-serialisable shipment dicts (API must hydrate to ShipmentTrace)."""
    return [
        {
            "shipment_id": "T050-COOL",
            "times_d": [0.0, 1.0, 2.0],
            "temps_c": [1.0, 1.0, 1.0],
            "duration_d": 2.0,
        },
        {
            "shipment_id": "T050-WARM",
            "times_d": [0.0, 1.0, 2.0],
            "temps_c": [5.0, 5.0, 5.0],
            "duration_d": 2.0,
        },
    ]


def _init_body(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "shipments": _json_shipments(),
        "n_particles": 32,
        "H": 3,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
    }
    cfg.update(overrides)
    return {"config": cfg, "seed": 7}


def _collect_keys(obj: Any, *, found: set[str] | None = None) -> set[str]:
    out = found if found is not None else set()
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            out.add(str(key))
            _collect_keys(value, found=out)
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for item in obj:
            _collect_keys(item, found=out)
    return out


def _assert_no_forbidden(payload: Any, *, label: str) -> None:
    forbidden = _collect_keys(payload) & _FORBIDDEN_PAYLOAD_KEYS
    assert not forbidden, (
        f"{label} must not contain forbidden presentation keys "
        f"{sorted(forbidden)} (ADR 0098 / T-050)"
    )


def _resolve_app() -> Any:
    try:
        mod = importlib.import_module(_API_PKG)
    except ImportError as exc:
        pytest.fail(
            f"{_API_PKG} must be importable (T-050 / ADR 0100 entry "
            f"`blueberries_voi.api:app`); got {exc!r}",
            pytrace=False,
        )
    app = getattr(mod, "app", None)
    if app is None:
        pytest.fail(
            f"{_API_PKG}.app must export the ASGI application (T-050 Interfaces)",
            pytrace=False,
        )
    return app


def _asgi_client(app: Any) -> Any:
    """Build a sync HTTP client against the ASGI app (Starlette/FastAPI/httpx)."""
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
    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
        # httpx stubs lag ASGITransport; runtime accepts it for TestClient fallback.
        return httpx.Client(
            transport=transport,  # type: ignore[arg-type]
            base_url="http://testserver",
        )
    except ImportError:
        pytest.fail(
            "T-050 optional extra [api] must install Starlette or FastAPI "
            "(and httpx for TestClient); cannot build an ASGI test client",
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
        f"POST {_SESSION_CREATE} must create a session; got {_status(resp)} "
        f"body={getattr(resp, 'text', resp)!r}"
    )
    payload = _response_json(resp)
    assert isinstance(payload, Mapping), "create session must return a JSON object"
    session_id = payload.get("session_id")
    assert isinstance(session_id, str) and session_id, (
        "create session response must include non-empty session_id"
    )
    return session_id


def _path(template: str, session_id: str) -> str:
    return template.format(session_id=session_id)


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".", maxsplit=1)[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", maxsplit=1)[0])
            imported.add(node.module)
    return imported


def _api_py_files() -> list[Path]:
    api_dir = _SRC / "api"
    if not api_dir.is_dir():
        pytest.fail(
            "src/blueberries_voi/api/ must exist as a package (T-050)",
            pytrace=False,
        )
    files = sorted(api_dir.rglob("*.py"))
    assert files, "api/ must contain at least one .py module"
    return files


# ---------------------------------------------------------------------------
# AC: optional extra [api]
# ---------------------------------------------------------------------------


def test_api_optional_extra_declares_asgi_stack() -> None:
    data = _load_pyproject()
    extras = data.get("project", {}).get("optional-dependencies", {})
    assert isinstance(extras, Mapping)
    assert "api" in extras, (
        "pyproject.toml must declare optional-dependencies.api "
        "(FastAPI or Starlette + JSON; ADR 0100 / T-050)"
    )
    reqs = [str(x).lower() for x in extras["api"]]
    joined = " ".join(reqs)
    assert "fastapi" in joined or "starlette" in joined, (
        f"[api] extra must install FastAPI or Starlette; got {extras['api']!r}"
    )


# ---------------------------------------------------------------------------
# AC: ASGI app importable + session-keyed EngineSession
# ---------------------------------------------------------------------------


def test_api_app_module_exports_asgi_app() -> None:
    app = _resolve_app()
    # ASGI callable: (scope, receive, send) or FastAPI/Starlette app with .routes
    assert callable(app) or hasattr(app, "routes") or hasattr(app, "router"), (
        "blueberries_voi.api:app must be an ASGI application"
    )


def test_create_session_returns_session_id() -> None:
    client = _asgi_client(_resolve_app())
    session_id = _create_session(client)
    assert re.fullmatch(r"[\w\-]+", session_id), (
        f"session_id should be a URL-safe token; got {session_id!r}"
    )


# ---------------------------------------------------------------------------
# AC: routes init / step / step_n / reset / act / delete
# ---------------------------------------------------------------------------


def test_init_returns_validated_snapshot() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    resp = client.post(_path(_INIT, sid), json=_init_body())
    assert _status(resp) == 200, (
        f"init must return 200; got {_status(resp)} {_response_json(resp)!r}"
    )
    snap = _response_json(resp)
    assert isinstance(snap, Mapping)
    validate_snapshot(snap)
    _assert_no_forbidden(snap, label="init Snapshot")


def test_step_returns_validated_day_delta() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_init_body())) == 200
    resp = client.post(_path(_STEP, sid), json={"order_qty": 0})
    assert _status(resp) == 200
    delta = _response_json(resp)
    assert isinstance(delta, Mapping)
    validate_day_delta(delta)
    _assert_no_forbidden(delta, label="step DayDelta")


def test_step_n_returns_framed_validated_deltas() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_init_body())) == 200
    orders = [0, 8, 0]
    resp = client.post(_path(_STEP_N, sid), json={"orders": orders})
    assert _status(resp) == 200
    payload = _response_json(resp)
    assert isinstance(payload, Mapping)
    assert "deltas" in payload, "step_n must return framed {deltas: DayDelta[]}"
    deltas = list(payload["deltas"])
    assert len(deltas) == len(orders)
    for i, delta in enumerate(deltas):
        assert isinstance(delta, Mapping)
        validate_day_delta(delta)
        _assert_no_forbidden(delta, label=f"step_n deltas[{i}]")


def test_reset_returns_validated_snapshot() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_init_body())) == 200
    resp = client.post(_path(_RESET, sid), json={})
    assert _status(resp) == 200
    snap = _response_json(resp)
    assert isinstance(snap, Mapping)
    validate_snapshot(snap)
    _assert_no_forbidden(snap, label="reset Snapshot")


def test_act_returns_validated_day_delta() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_init_body())) == 200
    resp = client.post(
        _path(_ACT, sid),
        json={"policy": "constant", "budgets": {"order_qty": 0}},
    )
    assert _status(resp) == 200
    delta = _response_json(resp)
    assert isinstance(delta, Mapping)
    validate_day_delta(delta)
    _assert_no_forbidden(delta, label="act DayDelta")


def test_delete_session_returns_204_then_unknown_is_404() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    resp = client.delete(_path(_SESSION_PATH, sid))
    assert _status(resp) == 204, f"DELETE session must return 204; got {_status(resp)}"
    missing = client.post(_path(_INIT, sid), json=_init_body())
    assert _status(missing) == 404


# ---------------------------------------------------------------------------
# AC: OpenAPI document available
# ---------------------------------------------------------------------------


def test_openapi_document_available_from_app() -> None:
    client = _asgi_client(_resolve_app())
    # FastAPI default; Starlette apps may mount an equivalent path or export.
    candidates = (
        "/openapi.json",
        "/api/openapi.json",
        "/docs/openapi.json",
    )
    last_status = None
    body: Any = None
    for path in candidates:
        resp = client.get(path)
        last_status = _status(resp)
        if last_status == 200:
            body = _response_json(resp)
            break
    if body is None:
        # Allow a Python-side openapi export on the module for non-FastAPI apps.
        mod = importlib.import_module(_API_PKG)
        for name in ("openapi", "OPENAPI", "get_openapi", "openapi_schema"):
            got = getattr(mod, name, None)
            if got is None:
                continue
            body = got() if callable(got) else got
            break
    assert body is not None, (
        "OpenAPI document must be available via GET /openapi.json "
        f"(tried {candidates}; last_status={last_status}) or "
        f"{_API_PKG}.openapi / get_openapi (T-050)"
    )
    assert isinstance(body, Mapping)
    # Paths for interactive protocol should appear in the document.
    paths = body.get("paths")
    assert isinstance(paths, Mapping), "OpenAPI must include a paths object"
    path_keys = " ".join(str(k) for k in paths)
    for needle in ("sessions", "init", "step"):
        assert needle in path_keys, (
            f"OpenAPI paths must cover session routes including {needle!r}; "
            f"got {sorted(paths)}"
        )


# ---------------------------------------------------------------------------
# AC: unknown session_id → 404 JSON error
# ---------------------------------------------------------------------------


def test_unknown_session_id_returns_404_json_error() -> None:
    client = _asgi_client(_resolve_app())
    resp = client.post(
        _path(_STEP, "no-such-session"),
        json={"order_qty": 0},
    )
    assert _status(resp) == 404
    body = _response_json(resp)
    assert isinstance(body, Mapping), "404 body must be JSON object"
    # T-049 error envelope or any explicit JSON error payload.
    has_envelope = (
        body.get("ok") is False
        and isinstance(body.get("error"), Mapping)
        and isinstance(body["error"].get("type"), str)
        and isinstance(body["error"].get("message"), str)
    )
    has_detail = "detail" in body or "error" in body or "message" in body
    assert has_envelope or has_detail, (
        "404 must include a JSON error body "
        "(envelope {ok:false,error:{type,message}} or field list / detail); "
        f"got {body!r}"
    )


# ---------------------------------------------------------------------------
# AC: invalid body → HTTP 4xx JSON field list or explicit error type
# ---------------------------------------------------------------------------


def test_step_missing_order_qty_returns_4xx_json_error() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_init_body())) == 200
    resp = client.post(_path(_STEP, sid), json={})
    assert 400 <= _status(resp) < 500, (
        f"missing order_qty must be HTTP 4xx; got {_status(resp)}"
    )
    body = _response_json(resp)
    assert isinstance(body, Mapping)
    text = json.dumps(body).lower()
    assert (
        "order_qty" in text
        or (
            isinstance(body.get("error"), Mapping)
            and isinstance(body["error"].get("type"), str)
        )
        or "fields" in body
        or "detail" in body
    ), (
        "4xx body must list invalid fields (e.g. order_qty) or an explicit "
        f"error type; got {body!r}"
    )


def test_step_n_missing_orders_returns_4xx_json_error() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_init_body())) == 200
    resp = client.post(_path(_STEP_N, sid), json={})
    assert 400 <= _status(resp) < 500
    body = _response_json(resp)
    assert isinstance(body, Mapping)
    text = json.dumps(body).lower()
    assert "orders" in text or "detail" in body or "error" in body, (
        f"missing orders must yield a JSON field/error payload; got {body!r}"
    )


# ---------------------------------------------------------------------------
# AC: api import graph does not require matplotlib
# ---------------------------------------------------------------------------


def test_api_modules_do_not_import_matplotlib() -> None:
    for path in _api_py_files():
        roots = _imported_roots(path)
        banned = roots & _FORBIDDEN_IMPORT_ROOTS
        assert not banned, (
            f"{_rel(path)} must not import {sorted(banned)} "
            "(T-050: interactive API routes must not require matplotlib)"
        )


def test_importing_api_app_does_not_import_matplotlib() -> None:
    """Importing the ASGI entry must not pull matplotlib into sys.modules."""
    import sys

    # Drop any prior matplotlib / api modules so the check is meaningful once
    # the package exists. If api is missing, _resolve_app fails for the right
    # reason first.
    for name in list(sys.modules):
        if name == "matplotlib" or name.startswith("matplotlib."):
            del sys.modules[name]
        if name == _API_PKG or name.startswith(f"{_API_PKG}."):
            del sys.modules[name]

    _resolve_app()
    assert "matplotlib" not in sys.modules, (
        "importing blueberries_voi.api must not load matplotlib "
        "(T-050 interactive serve path)"
    )

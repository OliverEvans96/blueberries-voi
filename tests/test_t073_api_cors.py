"""T-073 API CORS for local Vite → FastAPI — RED contracts.

Locks ``.team/specs/T-073.md`` and ADR 0108 (local dual-mode CORS).

Scope (local-dev only): allow Vite origins on ``localhost`` / ``127.0.0.1``
(typical ports including **5173**). Production CDN / auth CORS and wide ``*``
allowlists are out of scope for this ticket.

No CORSMiddleware in the app yet in this qa worktree — tests must fail for
missing CORS behaviour, not import typos in this file.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping
from typing import Any

import pytest

_API_PKG = "blueberries_voi.api"
_SESSION_CREATE = "/sessions"

# Local-dev Vite origins required by T-073 / ADR 0108.
_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _resolve_app() -> Any:
    try:
        mod = importlib.import_module(_API_PKG)
    except ImportError as exc:
        pytest.fail(
            f"{_API_PKG} must be importable (T-050 / ADR 0102); got {exc!r}",
            pytrace=False,
        )
    app = getattr(mod, "app", None)
    if app is None:
        pytest.fail(
            f"{_API_PKG}.app must export the ASGI application",
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
        return httpx.Client(
            transport=transport,  # type: ignore[arg-type]
            base_url="http://testserver",
        )
    except ImportError:
        pytest.fail(
            "optional extra [api] must install Starlette or FastAPI "
            "(and httpx for TestClient); cannot build an ASGI test client",
            pytrace=False,
        )


def _status(resp: Any) -> int:
    return int(resp.status_code)


def _headers(resp: Any) -> Mapping[str, str]:
    raw = getattr(resp, "headers", None)
    if raw is None:
        pytest.fail("response has no headers", pytrace=False)
    # Normalise to lowercase keys for CORS header lookups.
    return {str(k).lower(): str(v) for k, v in dict(raw).items()}


def _middleware_cls_names(app: Any) -> list[str]:
    """Collect middleware class names from a FastAPI/Starlette app."""
    names: list[str] = []
    for entry in getattr(app, "user_middleware", ()) or ():
        cls = getattr(entry, "cls", None)
        if cls is not None:
            names.append(cls.__name__)
            names.append(f"{cls.__module__}.{cls.__name__}")
    return names


# ---------------------------------------------------------------------------
# AC: CORSMiddleware (or equivalent) for localhost / 127.0.0.1 Vite
# ---------------------------------------------------------------------------


def test_app_installs_cors_middleware_for_local_vite() -> None:
    """FastAPI app must install CORSMiddleware (or Starlette equivalent)."""
    app = _resolve_app()
    names = _middleware_cls_names(app)
    assert any("CORSMiddleware" in n for n in names), (
        "app must add CORSMiddleware (ADR 0108 / T-073) allowing local Vite "
        f"origins {_ALLOWED_ORIGINS}; middleware seen={names!r}"
    )


@pytest.mark.parametrize("origin", _ALLOWED_ORIGINS)
def test_options_preflight_sessions_returns_cors_success_headers(
    origin: str,
) -> None:
    """OPTIONS preflight to /sessions from an allowed Origin succeeds."""
    client = _asgi_client(_resolve_app())
    resp = client.options(
        _SESSION_CREATE,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    status = _status(resp)
    assert status in {200, 204}, (
        f"OPTIONS {_SESSION_CREATE} preflight from {origin} must succeed; got {status}"
    )
    hdrs = _headers(resp)
    allow_origin = hdrs.get("access-control-allow-origin")
    assert allow_origin == origin, (
        "Access-Control-Allow-Origin must reflect the request Origin "
        f"(got {allow_origin!r}, expected {origin!r})"
    )
    allow_methods = hdrs.get("access-control-allow-methods", "")
    methods_upper = allow_methods.upper()
    assert "POST" in methods_upper, (
        f"Access-Control-Allow-Methods must include POST (got {allow_methods!r})"
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


@pytest.mark.parametrize("origin", _ALLOWED_ORIGINS)
def test_post_sessions_with_vite_origin_returns_allow_origin(
    origin: str,
) -> None:
    """POST /sessions with a local Vite Origin echoes Access-Control-Allow-Origin."""
    client = _asgi_client(_resolve_app())
    resp = client.post(_SESSION_CREATE, headers={"Origin": origin})
    status = _status(resp)
    assert status in {200, 201}, (
        f"POST {_SESSION_CREATE} must create a session; got {status} "
        f"body={getattr(resp, 'text', resp)!r}"
    )
    # Body must still be a valid session create (CORS must not break the route).
    payload = _response_json(resp)
    assert isinstance(payload, Mapping)
    session_id = payload.get("session_id")
    assert isinstance(session_id, str) and session_id, (
        "create session response must include non-empty session_id"
    )

    hdrs = _headers(resp)
    allow_origin = hdrs.get("access-control-allow-origin")
    assert allow_origin == origin, (
        "POST /sessions response must include Access-Control-Allow-Origin "
        f"matching {origin!r} (got {allow_origin!r})"
    )

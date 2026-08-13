"""T-051 HTTP/ASGI contract vs golden Snapshot / DayDelta — RED.

Locks ``.team/specs/T-051.md``: ASGI TestClient calls to ``init`` / ``step`` /
``step_n`` / ``reset`` / ``act`` validate with T-045 schema helpers, match
golden key sets + flat belief lengths, omit presentation keys, and publish
OpenAPI response schemas describing the same wire shapes (ADR 0100 / 0102).
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from blueberries_voi.simulator import DEMO_BUDGETS
from blueberries_voi.simulator.schema import (
    validate_day_delta,
    validate_snapshot,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "simulator"
_SNAPSHOT_GOLDEN = _FIXTURE_DIR / "snapshot_seed42.json"
_DAY_DELTA_GOLDEN = _FIXTURE_DIR / "day_delta_seed42_step0.json"
_STEP_N_GOLDEN = _FIXTURE_DIR / "step_n_seed42.json"

_API_PKG = "blueberries_voi.api"
_FIXED_SEED = 42

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
_FLAT_BELIEF_KEYS = frozenset({"lot_counts", "age_marginals", "tau_grid", "L", "K"})
_SNAPSHOT_REQUIRED = frozenset({"seq", "episode_day", "belief"})
_DAY_DELTA_REQUIRED = frozenset({"seq", "episode_day", "day", "drop_oldest"})

_SESSION_CREATE = "/sessions"
_INIT = "/sessions/{session_id}/init"
_STEP = "/sessions/{session_id}/step"
_STEP_N = "/sessions/{session_id}/step_n"
_RESET = "/sessions/{session_id}/reset"
_ACT = "/sessions/{session_id}/act"


def _load_json(path: Path) -> Any:
    assert path.is_file(), f"missing golden fixture: {path.relative_to(_REPO_ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def _json_shipments() -> list[dict[str, Any]]:
    """Match T-045 golden README recipe shipment traces (JSON form)."""
    return [
        {
            "shipment_id": "T045-COOL",
            "times_d": [0.0, 1.0, 2.0],
            "temps_c": [1.0, 1.0, 1.0],
            "duration_d": 2.0,
        },
        {
            "shipment_id": "T045-WARM",
            "times_d": [0.0, 1.0, 2.0],
            "temps_c": [5.0, 5.0, 5.0],
            "duration_d": 2.0,
        },
    ]


def _golden_init_body(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "shipments": _json_shipments(),
        "n_particles": int(DEMO_BUDGETS["n_particles"]),
        "H": int(DEMO_BUDGETS["H"]),
        "n_rollout_paths": int(DEMO_BUDGETS["n_rollout_paths"]),
        "candidate_case_radius": int(DEMO_BUDGETS["candidate_case_radius"]),
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
    }
    cfg.update(overrides)
    return {"config": cfg, "seed": _FIXED_SEED}


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
        f"{sorted(forbidden)} (ADR 0100 / T-051)"
    )


def _assert_flat_belief_lengths(belief: Mapping[str, Any], *, label: str) -> None:
    missing = _FLAT_BELIEF_KEYS - set(belief)
    assert not missing, f"{label} missing flat belief fields {sorted(missing)}"
    l_dim = int(belief["L"])
    k_dim = int(belief["K"])
    assert len(list(belief["lot_counts"])) == l_dim
    assert len(list(belief["age_marginals"])) == l_dim * k_dim
    assert len(list(belief["tau_grid"])) == k_dim


def _assert_shape_parity_with_golden(
    live: Mapping[str, Any],
    golden: Mapping[str, Any],
    *,
    label: str,
    required: frozenset[str],
) -> None:
    """Schema parity: key sets + belief flat lengths (seq may differ)."""
    assert set(live) >= required, f"{label} missing {sorted(required - set(live))}"
    assert set(live) == set(golden), (
        f"{label} key set must match golden; "
        f"live={sorted(live)} golden={sorted(golden)}"
    )
    if "belief" in live and live["belief"] is not None:
        assert isinstance(live["belief"], Mapping)
        assert isinstance(golden["belief"], Mapping)
        assert set(live["belief"]) == set(golden["belief"]), (
            f"{label}.belief keys must match golden"
        )
        _assert_flat_belief_lengths(live["belief"], label=f"{label}.belief")
        _assert_flat_belief_lengths(golden["belief"], label=f"{label} golden.belief")
        assert int(live["belief"]["L"]) == int(golden["belief"]["L"])
        assert int(live["belief"]["K"]) == int(golden["belief"]["K"])


def _resolve_app() -> Any:
    try:
        mod = importlib.import_module(_API_PKG)
    except ImportError as exc:
        pytest.fail(
            f"{_API_PKG} must be importable (T-050/T-051); got {exc!r}",
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
    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
        return httpx.Client(
            transport=transport,  # type: ignore[arg-type]
            base_url="http://testserver",
        )
    except ImportError:
        pytest.fail(
            "ASGI TestClient requires Starlette/FastAPI + httpx (T-050 [api] extra)",
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
    assert _status(resp) in {200, 201}
    payload = _response_json(resp)
    assert isinstance(payload, Mapping)
    session_id = payload.get("session_id")
    assert isinstance(session_id, str) and session_id
    return session_id


def _path(template: str, session_id: str) -> str:
    return template.format(session_id=session_id)


def _openapi_document(client: Any) -> Mapping[str, Any]:
    candidates = ("/openapi.json", "/api/openapi.json", "/docs/openapi.json")
    for path in candidates:
        resp = client.get(path)
        if _status(resp) == 200:
            body = _response_json(resp)
            assert isinstance(body, Mapping)
            return body
    mod = importlib.import_module(_API_PKG)
    for name in ("openapi", "OPENAPI", "get_openapi", "openapi_schema"):
        got = getattr(mod, name, None)
        if got is None:
            continue
        body = got() if callable(got) else got
        assert isinstance(body, Mapping)
        return body
    pytest.fail(
        "OpenAPI document must be available for T-051 contract checks "
        f"(tried {candidates} and {_API_PKG}.openapi helpers)",
        pytrace=False,
    )


def _resolve_schema_ref(doc: Mapping[str, Any], node: Any) -> Mapping[str, Any]:
    """Resolve a (possibly $ref) schema node to a mapping with properties."""
    assert isinstance(node, Mapping), f"schema node must be object; got {type(node)!r}"
    if "$ref" in node:
        ref = str(node["$ref"])
        assert ref.startswith("#/components/schemas/"), (
            f"OpenAPI $ref must point at components/schemas; got {ref!r}"
        )
        name = ref.rsplit("/", maxsplit=1)[-1]
        schemas = doc.get("components", {}).get("schemas", {})
        assert isinstance(schemas, Mapping) and name in schemas, (
            f"OpenAPI missing components.schemas.{name} (T-051 / ADR 0102)"
        )
        resolved = schemas[name]
        assert isinstance(resolved, Mapping)
        return resolved
    return node


def _response_schema_for(
    doc: Mapping[str, Any], *, path: str, method: str = "post"
) -> Mapping[str, Any]:
    paths = doc.get("paths")
    assert isinstance(paths, Mapping), "OpenAPI must include paths"
    assert path in paths, f"OpenAPI missing path {path!r}; have {sorted(paths)}"
    op = paths[path]
    assert isinstance(op, Mapping)
    method_body = op.get(method)
    assert isinstance(method_body, Mapping), f"OpenAPI {path} missing {method}"
    responses = method_body.get("responses")
    assert isinstance(responses, Mapping)
    ok = responses.get("200") or responses.get("201")
    assert isinstance(ok, Mapping), f"OpenAPI {path} missing 200/201 response"
    content = ok.get("content")
    assert isinstance(content, Mapping)
    app_json = content.get("application/json")
    assert isinstance(app_json, Mapping), f"OpenAPI {path} 200 must be application/json"
    schema = app_json.get("schema")
    assert isinstance(schema, Mapping), f"OpenAPI {path} 200 missing schema"
    return _resolve_schema_ref(doc, schema)


def _assert_openapi_object_keys(
    schema: Mapping[str, Any],
    *,
    required_keys: frozenset[str],
    label: str,
) -> None:
    """Schema must name golden-required properties (not a bare additionalProperties)."""
    # Unwrap allOf / anyOf singletons commonly emitted by FastAPI.
    for wrapper in ("allOf", "anyOf", "oneOf"):
        parts = schema.get(wrapper)
        if (
            isinstance(parts, list)
            and len(parts) == 1
            and isinstance(parts[0], Mapping)
        ):
            schema = parts[0]
            break

    props = schema.get("properties")
    assert isinstance(props, Mapping), (
        f"{label}: OpenAPI must declare properties matching golden keys "
        f"(got type={schema.get('type')!r} additionalProperties="
        f"{schema.get('additionalProperties')!r}); ADR 0102 requires schemas "
        f"used by golden fixtures"
    )
    prop_keys = {str(k) for k in props}
    missing = required_keys - prop_keys
    assert not missing, (
        f"{label}: OpenAPI properties missing golden-required keys {sorted(missing)}; "
        f"have {sorted(prop_keys)}"
    )
    # Forbidden presentation keys must not appear as declared properties.
    forbidden = prop_keys & _FORBIDDEN_PAYLOAD_KEYS
    assert not forbidden, (
        f"{label}: OpenAPI must not declare presentation properties {sorted(forbidden)}"
    )


# ---------------------------------------------------------------------------
# AC: HTTP init / step / step_n / reset / act + T-045 validators
# ---------------------------------------------------------------------------


def test_http_init_validates_with_t045_schema_helpers() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    resp = client.post(_path(_INIT, sid), json=_golden_init_body())
    assert _status(resp) == 200
    snap = _response_json(resp)
    assert isinstance(snap, Mapping)
    validate_snapshot(snap)
    _assert_no_forbidden(snap, label="HTTP init Snapshot")


def test_http_step_validates_with_t045_schema_helpers() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_golden_init_body())) == 200
    resp = client.post(_path(_STEP, sid), json={"order_qty": 16})
    assert _status(resp) == 200
    delta = _response_json(resp)
    assert isinstance(delta, Mapping)
    validate_day_delta(delta)
    _assert_no_forbidden(delta, label="HTTP step DayDelta")


def test_http_reset_validates_with_t045_schema_helpers() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_golden_init_body())) == 200
    resp = client.post(_path(_RESET, sid), json={})
    assert _status(resp) == 200
    snap = _response_json(resp)
    assert isinstance(snap, Mapping)
    validate_snapshot(snap)
    _assert_no_forbidden(snap, label="HTTP reset Snapshot")


def test_http_act_validates_with_t045_schema_helpers() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_golden_init_body())) == 200
    resp = client.post(
        _path(_ACT, sid),
        json={"policy": "constant", "budgets": {"order_qty": 0}},
    )
    assert _status(resp) == 200
    delta = _response_json(resp)
    assert isinstance(delta, Mapping)
    validate_day_delta(delta)
    _assert_no_forbidden(delta, label="HTTP act DayDelta")


# ---------------------------------------------------------------------------
# AC: HTTP shapes vs golden fixtures (key sets + belief lengths)
# ---------------------------------------------------------------------------


def test_http_snapshot_shape_matches_golden_key_sets_and_belief_lengths() -> None:
    golden = _load_json(_SNAPSHOT_GOLDEN)
    assert isinstance(golden, Mapping)
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    resp = client.post(_path(_INIT, sid), json=_golden_init_body())
    assert _status(resp) == 200
    snap = _response_json(resp)
    assert isinstance(snap, Mapping)
    validate_snapshot(snap)
    _assert_shape_parity_with_golden(
        snap,
        golden,
        label="HTTP Snapshot",
        required=_SNAPSHOT_REQUIRED,
    )


def test_http_day_delta_shape_matches_golden_key_sets_and_belief_lengths() -> None:
    golden = _load_json(_DAY_DELTA_GOLDEN)
    assert isinstance(golden, Mapping)
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_golden_init_body())) == 200
    resp = client.post(_path(_STEP, sid), json={"order_qty": 16})
    assert _status(resp) == 200
    delta = _response_json(resp)
    assert isinstance(delta, Mapping)
    validate_day_delta(delta)
    _assert_shape_parity_with_golden(
        delta,
        golden,
        label="HTTP DayDelta",
        required=_DAY_DELTA_REQUIRED,
    )


# ---------------------------------------------------------------------------
# AC: forbidden presentation keys absent from every interactive response
# ---------------------------------------------------------------------------


def test_every_interactive_http_response_omits_presentation_keys() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    responses: list[tuple[str, Any]] = []

    init_resp = client.post(_path(_INIT, sid), json=_golden_init_body())
    assert _status(init_resp) == 200
    responses.append(("init", _response_json(init_resp)))

    step_resp = client.post(_path(_STEP, sid), json={"order_qty": 0})
    assert _status(step_resp) == 200
    responses.append(("step", _response_json(step_resp)))

    step_n_resp = client.post(_path(_STEP_N, sid), json={"orders": [0, 8, 0]})
    assert _status(step_n_resp) == 200
    responses.append(("step_n", _response_json(step_n_resp)))

    reset_resp = client.post(_path(_RESET, sid), json={})
    assert _status(reset_resp) == 200
    responses.append(("reset", _response_json(reset_resp)))

    act_resp = client.post(
        _path(_ACT, sid),
        json={"policy": "constant", "budgets": {"order_qty": 0}},
    )
    assert _status(act_resp) == 200
    responses.append(("act", _response_json(act_resp)))

    for label, payload in responses:
        _assert_no_forbidden(payload, label=f"HTTP {label}")
        if label == "step_n":
            assert isinstance(payload, Mapping)
            for i, delta in enumerate(payload["deltas"]):
                _assert_no_forbidden(delta, label=f"HTTP step_n deltas[{i}]")


# ---------------------------------------------------------------------------
# AC: step_n with three orders → three deltas
# ---------------------------------------------------------------------------


def test_http_step_n_three_orders_returns_three_validated_deltas() -> None:
    golden_framed = _load_json(_STEP_N_GOLDEN)
    assert isinstance(golden_framed, Mapping)
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_golden_init_body())) == 200
    orders = [0, 16, 0]
    resp = client.post(_path(_STEP_N, sid), json={"orders": orders})
    assert _status(resp) == 200
    payload = _response_json(resp)
    assert isinstance(payload, Mapping)
    assert "deltas" in payload, "step_n must return framed {deltas: DayDelta[]}"
    deltas = list(payload["deltas"])
    assert len(deltas) == 3, (
        f"step_n with three orders must return three deltas; got {len(deltas)}"
    )
    golden_deltas = list(golden_framed["deltas"])
    assert len(golden_deltas) == 3
    for i, delta in enumerate(deltas):
        assert isinstance(delta, Mapping)
        validate_day_delta(delta)
        _assert_no_forbidden(delta, label=f"HTTP step_n[{i}]")
        _assert_shape_parity_with_golden(
            delta,
            golden_deltas[i],
            label=f"HTTP step_n[{i}]",
            required=_DAY_DELTA_REQUIRED,
        )


# ---------------------------------------------------------------------------
# AC: failure paths — bad session → 404; malformed step → 4xx
# ---------------------------------------------------------------------------


def test_http_unknown_session_id_returns_404() -> None:
    client = _asgi_client(_resolve_app())
    resp = client.post(
        _path(_STEP, "no-such-session-t051"),
        json={"order_qty": 0},
    )
    assert _status(resp) == 404
    body = _response_json(resp)
    assert isinstance(body, Mapping), "404 body must be JSON"


def test_http_malformed_step_body_returns_4xx() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_golden_init_body())) == 200
    resp = client.post(_path(_STEP, sid), json={})
    assert 400 <= _status(resp) < 500, (
        f"malformed step body must be HTTP 4xx; got {_status(resp)}"
    )
    body = _response_json(resp)
    assert isinstance(body, Mapping), "4xx body must be JSON"


def test_http_step_wrong_type_order_qty_returns_4xx() -> None:
    client = _asgi_client(_resolve_app())
    sid = _create_session(client)
    assert _status(client.post(_path(_INIT, sid), json=_golden_init_body())) == 200
    resp = client.post(_path(_STEP, sid), json={"order_qty": "not-an-int"})
    assert 400 <= _status(resp) < 500
    body = _response_json(resp)
    assert isinstance(body, Mapping)


# ---------------------------------------------------------------------------
# AC / ADR 0102: OpenAPI describes the same schemas as golden fixtures
# ---------------------------------------------------------------------------


def test_openapi_declares_snapshot_schema_matching_golden_keys() -> None:
    """Response schemas must name Snapshot fields — not bare additionalProperties."""
    golden = _load_json(_SNAPSHOT_GOLDEN)
    assert isinstance(golden, Mapping)
    client = _asgi_client(_resolve_app())
    doc = _openapi_document(client)
    schemas = doc.get("components", {}).get("schemas", {})
    assert isinstance(schemas, Mapping)
    # Prefer a named Snapshot component; fall back to resolving the init 200 schema.
    if "Snapshot" in schemas:
        schema = _resolve_schema_ref(doc, {"$ref": "#/components/schemas/Snapshot"})
    else:
        schema = _response_schema_for(
            doc, path="/sessions/{session_id}/init", method="post"
        )
    _assert_openapi_object_keys(
        schema,
        required_keys=_SNAPSHOT_REQUIRED,
        label="OpenAPI Snapshot",
    )
    # Belief sub-object must expose flat buffer fields when declared.
    props = schema.get("properties")
    if isinstance(props, Mapping) and "belief" in props:
        belief_schema = _resolve_schema_ref(doc, props["belief"])
        belief_props = belief_schema.get("properties")
        if belief_props is None and "$ref" not in props["belief"]:
            # Still require top-level Snapshot keys; belief detail may be $ref.
            pass
        else:
            if not isinstance(belief_props, Mapping):
                belief_schema = _resolve_schema_ref(doc, props["belief"])
                belief_props = belief_schema.get("properties")
            assert isinstance(belief_props, Mapping), (
                "OpenAPI Snapshot.belief must declare properties "
                f"(flat L / L*K / K) matching golden; got {belief_schema!r}"
            )
            missing = _FLAT_BELIEF_KEYS - {str(k) for k in belief_props}
            assert not missing, f"OpenAPI Snapshot.belief missing {sorted(missing)}"


def test_openapi_declares_day_delta_schema_matching_golden_keys() -> None:
    golden = _load_json(_DAY_DELTA_GOLDEN)
    assert isinstance(golden, Mapping)
    client = _asgi_client(_resolve_app())
    doc = _openapi_document(client)
    schemas = doc.get("components", {}).get("schemas", {})
    assert isinstance(schemas, Mapping)
    if "DayDelta" in schemas:
        schema = _resolve_schema_ref(doc, {"$ref": "#/components/schemas/DayDelta"})
    else:
        schema = _response_schema_for(
            doc, path="/sessions/{session_id}/step", method="post"
        )
    _assert_openapi_object_keys(
        schema,
        required_keys=_DAY_DELTA_REQUIRED,
        label="OpenAPI DayDelta",
    )


def test_openapi_step_n_response_schema_frames_day_delta_list() -> None:
    client = _asgi_client(_resolve_app())
    doc = _openapi_document(client)
    schemas = doc.get("components", {}).get("schemas", {})
    assert isinstance(schemas, Mapping)
    if "StepNResponse" in schemas or "StepNFrame" in schemas:
        name = "StepNResponse" if "StepNResponse" in schemas else "StepNFrame"
        schema = _resolve_schema_ref(doc, {"$ref": f"#/components/schemas/{name}"})
    else:
        schema = _response_schema_for(
            doc, path="/sessions/{session_id}/step_n", method="post"
        )
    props = schema.get("properties")
    assert isinstance(props, Mapping), (
        "OpenAPI step_n 200 schema must declare properties including 'deltas' "
        f"(framed list); got {schema!r}"
    )
    assert "deltas" in props, (
        "OpenAPI step_n response must include 'deltas' matching golden "
        "tests/fixtures/simulator/step_n_seed42.json"
    )

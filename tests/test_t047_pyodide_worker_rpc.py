"""T-047 Pyodide worker RPC + browser demo budget smoke (RED).

Locks ``.team/specs/T-047.md``, ADR 0098 (JSON wire / no deep toJs), ADR 0097
(dialed demo budgets), and ADR 0099 (Pyodide 314.0.4, worker-only).

Worker / smoke artifacts live **outside** ``src/blueberries_voi/`` (M2 closeout
still forbids ``*pyodide*`` / ``*wasm*`` modules under ``src/``). Tests fail for
missing worker/API or wrong protocol — not import typos in this file.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest

from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator import DEMO_BUDGETS

if TYPE_CHECKING:
    from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src" / "blueberries_voi"

_PYODIDE_PIN = "314.0.4"

_RPC_METHODS = frozenset({"init", "step", "step_n", "reset", "act"})

# Spec default: scaffold smoke in this repo under web/ or packaging/pyodide/.
_WORKER_CANDIDATES = (
    _REPO_ROOT / "packaging" / "pyodide" / "worker.js",
    _REPO_ROOT / "packaging" / "pyodide" / "engine_worker.js",
    _REPO_ROOT / "packaging" / "pyodide" / "worker.mjs",
    _REPO_ROOT / "web" / "pyodide" / "worker.js",
    _REPO_ROOT / "web" / "worker.js",
    _REPO_ROOT / "browser" / "pyodide_worker.js",
)

_MAIN_THREAD_HARNESS_CANDIDATES = (
    _REPO_ROOT / "packaging" / "pyodide" / "main.js",
    _REPO_ROOT / "packaging" / "pyodide" / "smoke_main.js",
    _REPO_ROOT / "packaging" / "pyodide" / "host.js",
    _REPO_ROOT / "web" / "pyodide" / "main.js",
    _REPO_ROOT / "web" / "smoke" / "main.js",
    _REPO_ROOT / "web" / "smoke.js",
)

_SMOKE_SCRIPT_CANDIDATES = (
    _REPO_ROOT / "scripts" / "smoke_pyodide_worker.py",
    _REPO_ROOT / "scripts" / "smoke_pyodide_budget.py",
    _REPO_ROOT / "packaging" / "pyodide" / "smoke.py",
    _REPO_ROOT / "packaging" / "pyodide" / "smoke_budget.py",
    _REPO_ROOT / "packaging" / "pyodide" / "smoke.sh",
    _REPO_ROOT / "web" / "smoke_pyodide.sh",
)

# Python-side RPC mirror of the worker edge (JSON in / JSON out) for contract
# tests without requiring a live browser. Implementer lands this next to the
# worker; worker bootstraps the same EngineSession binding.
_RPC_MODULE_CANDIDATES = (
    _REPO_ROOT / "packaging" / "pyodide" / "session_rpc.py",
    _REPO_ROOT / "packaging" / "pyodide" / "rpc.py",
    _REPO_ROOT / "web" / "pyodide" / "session_rpc.py",
)

_DOC_CANDIDATES = (
    _REPO_ROOT / "packaging" / "pyodide" / "README.md",
    _REPO_ROOT / "packaging" / "README.md",
    _REPO_ROOT / "docs" / "pyodide.md",
    _REPO_ROOT / "docs" / "browser.md",
    _REPO_ROOT / "web" / "README.md",
)

_DEMO_N_CAP = 200
_DEMO_H_CAP = 7
_DEMO_PATHS_CAP = 2
_DEMO_RADIUS_CAP = 1

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


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _first_existing(candidates: tuple[Path, ...]) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def _require_file(candidates: tuple[Path, ...], *, what: str) -> Path:
    found = _first_existing(candidates)
    if found is not None:
        return found
    tried = ", ".join(_rel(p) for p in candidates)
    pytest.fail(
        f"T-047 {what} missing; expected one of: {tried}",
        pytrace=False,
    )


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T047-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="T047-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _demo_config(**overrides: Any) -> dict[str, Any]:
    """Dialed demo budgets (≤ ADR 0097 caps); never production N=2000."""
    cfg: dict[str, Any] = {
        "shipments": _fixture_shipments(),
        "n_particles": int(DEMO_BUDGETS["n_particles"]),
        "H": int(DEMO_BUDGETS["H"]),
        "n_rollout_paths": int(DEMO_BUDGETS["n_rollout_paths"]),
        "candidate_case_radius": int(DEMO_BUDGETS["candidate_case_radius"]),
        "L": 2,
        "K": 4,
        "enable_filter": True,
    }
    cfg.update(overrides)
    return cfg


def _assert_demo_budgets(cfg: Mapping[str, Any]) -> None:
    assert int(cfg["n_particles"]) <= _DEMO_N_CAP
    assert int(cfg["H"]) <= _DEMO_H_CAP
    assert int(cfg["n_rollout_paths"]) <= _DEMO_PATHS_CAP
    assert int(cfg["candidate_case_radius"]) <= _DEMO_RADIUS_CAP
    assert int(cfg["n_particles"]) < 2000, (
        "smoke must use dialed demo budgets, not production N=2000"
    )


def _load_rpc_module() -> ModuleType:
    path = _require_file(_RPC_MODULE_CANDIDATES, what="session RPC module")
    name = f"_t047_session_rpc_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load RPC module from {_rel(path)}", pytrace=False)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        pytest.fail(
            f"RPC module {_rel(path)} failed to import: {exc}",
            pytrace=False,
        )
    return mod


def _rpc_handle(mod: ModuleType, request: Mapping[str, Any]) -> Any:
    """Call the documented JSON RPC entry; accept str or mapping result."""
    for attr in ("handle_rpc", "dispatch", "handle", "rpc"):
        fn = getattr(mod, attr, None)
        if callable(fn):
            return fn(request)
    # Class-style: WorkerSession / SessionRpc with handle_rpc
    for cls_name in ("SessionRpc", "WorkerRpc", "EngineRpc", "PyodideSessionRpc"):
        cls = getattr(mod, cls_name, None)
        if cls is None:
            continue
        try:
            inst = cls()
        except TypeError:
            continue
        for attr in ("handle_rpc", "dispatch", "handle", "rpc"):
            fn = getattr(inst, attr, None)
            if callable(fn):
                return fn(request)
    pytest.fail(
        "RPC module must expose handle_rpc/dispatch/handle/rpc "
        "(function or SessionRpc-like class) that accepts the worker request "
        "object {id, method, params}",
        pytrace=False,
    )


def _as_response(raw: Any) -> dict[str, Any]:
    """Normalize RPC result to a plain dict (JSON string or cloneable object)."""
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"RPC must return JSON string or object; got invalid JSON: {exc}"
            )
        assert isinstance(decoded, dict), (
            f"decoded RPC JSON must be an object, got {type(decoded)!r}"
        )
        return decoded
    if isinstance(raw, Mapping):
        # Must be structured-clone / json.dumps safe — no exotic proxies.
        try:
            encoded = json.dumps(raw)
        except (TypeError, ValueError) as exc:
            pytest.fail(
                "RPC mapping result must be JSON-serialisable (no nested PyProxy / "
                f"non-cloneable values): {exc}",
                pytrace=False,
            )
        out = json.loads(encoded)
        assert isinstance(out, dict)
        return out
    pytest.fail(
        "RPC response must be a JSON string or plain JSON-cloneable object; "
        f"got {type(raw)!r}",
        pytrace=False,
    )


def _assert_ok_response(resp: Mapping[str, Any], *, req_id: str) -> Any:
    assert resp.get("id") == req_id, f"response.id must echo request id {req_id!r}"
    assert "ok" in resp, "response must include boolean ok"
    if resp["ok"] is True:
        assert "result" in resp, "ok response must include result"
        assert "error" not in resp or resp["error"] is None
        return resp["result"]
    assert resp["ok"] is False
    err = resp.get("error")
    assert isinstance(err, Mapping), "error response must include error object"
    assert "type" in err and "message" in err
    pytest.fail(f"RPC returned error: {err.get('type')}: {err.get('message')}")


def _assert_no_forbidden_keys(obj: Any, *, label: str) -> None:
    if isinstance(obj, Mapping):
        bad = _FORBIDDEN_PAYLOAD_KEYS & set(obj)
        assert not bad, f"{label} contains forbidden wire keys {sorted(bad)}"
        for k, v in obj.items():
            _assert_no_forbidden_keys(v, label=f"{label}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_forbidden_keys(item, label=f"{label}[{i}]")


def _assert_not_pyproxy_marker(obj: Any, *, label: str) -> None:
    """Contract guard: results must not look like Pyodide PyProxy / FFI handles."""
    type_name = type(obj).__name__
    assert "PyProxy" not in type_name, (
        f"{label}: nested PyProxy must not cross the worker→main boundary "
        f"(got {type_name})"
    )
    # Common string markers if someone accidentally str()'d a proxy
    if isinstance(obj, str) and "PyProxy" in obj:
        pytest.fail(f"{label}: string payload mentions PyProxy — not plain JSON")
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            _assert_not_pyproxy_marker(v, label=f"{label}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_not_pyproxy_marker(item, label=f"{label}[{i}]")


# ---------------------------------------------------------------------------
# AC: worker script path + Pyodide pin + EngineSession + RPC methods
# ---------------------------------------------------------------------------


def test_worker_script_exists_outside_src() -> None:
    """Worker JS lives under packaging/pyodide/ or web/ — not src/."""
    worker = _require_file(_WORKER_CANDIDATES, what="Pyodide worker script")
    under_src = _SRC in worker.parents or str(worker).startswith(str(_SRC))
    assert not under_src, (
        "worker must not live under src/blueberries_voi/ (M2 closeout); "
        f"got {_rel(worker)}"
    )


def test_no_pyodide_or_wasm_modules_under_src() -> None:
    """T-047 must not introduce *pyodide* / *wasm* packages under src/."""
    hits = [
        p
        for p in list(_SRC.rglob("*pyodide*")) + list(_SRC.rglob("*wasm*"))
        if p.is_file()
    ]
    assert not hits, (
        "M2 closeout: no *pyodide* / *wasm* modules under src/; put worker under "
        "packaging/pyodide/ or web/. Found: " + ", ".join(_rel(p) for p in hits)
    )


def test_worker_pins_pyodide_314_and_binds_engine_session() -> None:
    worker = _require_file(_WORKER_CANDIDATES, what="Pyodide worker script")
    text = worker.read_text(encoding="utf-8")
    assert _PYODIDE_PIN in text, (
        f"worker {_rel(worker)} must load/pin Pyodide {_PYODIDE_PIN} (ADR 0099)"
    )
    assert re.search(r"micropip|loadPyodide|pyodide", text, re.I), (
        f"worker {_rel(worker)} must load Pyodide / micropip install path"
    )
    assert re.search(r"EngineSession", text), (
        f"worker {_rel(worker)} must construct/bind one EngineSession"
    )
    for method in sorted(_RPC_METHODS):
        assert re.search(rf"\b{method}\b", text), (
            f"worker {_rel(worker)} must answer RPC method {method!r}"
        )


def test_worker_or_docs_mention_slim_release_wheel_install() -> None:
    worker = _require_file(_WORKER_CANDIDATES, what="Pyodide worker script")
    texts = [worker.read_text(encoding="utf-8")]
    for doc in _DOC_CANDIDATES:
        if doc.is_file():
            texts.append(doc.read_text(encoding="utf-8"))
    blob = "\n".join(texts)
    assert re.search(
        r"micropip\.install|releases/download|slim\s+wheel|browser\s+wheel",
        blob,
        re.I,
    ), (
        "worker or packaging/pyodide docs must describe Release/slim wheel install "
        "via micropip (T-046 / ADR 0099)"
    )


# ---------------------------------------------------------------------------
# AC: worker message protocol
# ---------------------------------------------------------------------------


def test_worker_message_protocol_documented_in_worker_or_rpc_module() -> None:
    """Request/response shapes from T-047 Interfaces must appear in artifacts."""
    chunks: list[str] = []
    worker = _first_existing(_WORKER_CANDIDATES)
    if worker is not None:
        chunks.append(worker.read_text(encoding="utf-8"))
    rpc_path = _first_existing(_RPC_MODULE_CANDIDATES)
    if rpc_path is not None:
        chunks.append(rpc_path.read_text(encoding="utf-8"))
    # Prefer worker-local README over the T-046 packaging overview.
    for doc in (
        _REPO_ROOT / "packaging" / "pyodide" / "README.md",
        _REPO_ROOT / "web" / "README.md",
        _REPO_ROOT / "docs" / "pyodide.md",
        _REPO_ROOT / "docs" / "browser.md",
    ):
        if doc.is_file():
            chunks.append(doc.read_text(encoding="utf-8"))
    if not chunks:
        pytest.fail(
            "T-047 worker / session RPC module / pyodide docs missing — "
            "cannot document {id, method, params} / {ok, result|error} protocol",
            pytrace=False,
        )
    blob = "\n".join(chunks)
    required = ("method", "ok", "result", "error", "init", "step_n", "params")
    missing = [tok for tok in required if tok not in blob]
    assert not missing, (
        "protocol artifacts must mention request/response fields "
        f"{sorted(required)}; missing {missing}"
    )


def test_rpc_init_step_step_n_reset_act_json_protocol() -> None:
    """Bound EngineSession via JSON RPC: init / step / step_n / reset / act."""
    mod = _load_rpc_module()
    cfg = _demo_config()
    _assert_demo_budgets(cfg)

    # Shipments are Python objects — RPC edge must accept JSON-cloneable config.
    # Implementer may accept a serialisable stand-in; for contract tests we pass
    # a JSON-friendly config plus an optional shipments hook on the module.
    wire_cfg = {k: v for k, v in cfg.items() if k != "shipments"}
    prepare = getattr(mod, "prepare_demo_config", None)
    if callable(prepare):
        wire_cfg = prepare(wire_cfg, shipments=_fixture_shipments())
    else:
        # Allow module-level default demo shipments when params omit them.
        wire_cfg = dict(wire_cfg)

    init_id = "req-init-1"
    init_resp = _as_response(
        _rpc_handle(
            mod,
            {
                "id": init_id,
                "method": "init",
                "params": {"config": wire_cfg, "seed": 47},
            },
        )
    )
    snap = _assert_ok_response(init_resp, req_id=init_id)
    assert isinstance(snap, Mapping)
    assert {"seq", "episode_day", "belief"} <= set(snap)
    _assert_no_forbidden_keys(snap, label="Snapshot")
    _assert_not_pyproxy_marker(snap, label="Snapshot")

    step_id = "req-step-1"
    step_resp = _as_response(
        _rpc_handle(
            mod,
            {"id": step_id, "method": "step", "params": {"order_qty": 1}},
        )
    )
    delta = _assert_ok_response(step_resp, req_id=step_id)
    assert isinstance(delta, Mapping)
    assert {"seq", "episode_day", "day"} <= set(delta)
    _assert_no_forbidden_keys(delta, label="DayDelta")
    _assert_not_pyproxy_marker(delta, label="DayDelta")

    step_n_id = "req-stepn-1"
    orders = [1, 0]
    step_n_resp = _as_response(
        _rpc_handle(
            mod,
            {
                "id": step_n_id,
                "method": "step_n",
                "params": {"orders": orders},
            },
        )
    )
    step_n_result = _assert_ok_response(step_n_resp, req_id=step_n_id)
    if isinstance(step_n_result, list):
        deltas = step_n_result
    elif isinstance(step_n_result, Mapping) and "deltas" in step_n_result:
        deltas = list(step_n_result["deltas"])
    else:
        pytest.fail("step_n result must be list[DayDelta] or {deltas: [...]}")
    assert len(deltas) >= 2, "step_n smoke requires ≥2 orders"
    assert len(deltas) == len(orders)
    for i, d in enumerate(deltas):
        assert isinstance(d, Mapping)
        _assert_no_forbidden_keys(d, label=f"DayDelta[{i}]")
        _assert_not_pyproxy_marker(d, label=f"DayDelta[{i}]")

    reset_id = "req-reset-1"
    reset_resp = _as_response(
        _rpc_handle(
            mod,
            {"id": reset_id, "method": "reset", "params": {}},
        )
    )
    reset_snap = _assert_ok_response(reset_resp, req_id=reset_id)
    assert isinstance(reset_snap, Mapping)
    assert {"seq", "episode_day", "belief"} <= set(reset_snap)

    act_id = "req-act-1"
    act_resp = _as_response(
        _rpc_handle(
            mod,
            {"id": act_id, "method": "act", "params": {}},
        )
    )
    act_delta = _assert_ok_response(act_resp, req_id=act_id)
    assert isinstance(act_delta, Mapping)
    assert {"seq", "episode_day", "day"} <= set(act_delta)


def test_rpc_error_envelope_for_unknown_method() -> None:
    mod = _load_rpc_module()
    resp = _as_response(
        _rpc_handle(
            mod,
            {"id": "err-1", "method": "not_a_method", "params": {}},
        )
    )
    assert resp.get("id") == "err-1"
    assert resp.get("ok") is False
    err = resp.get("error")
    assert isinstance(err, Mapping)
    assert isinstance(err.get("type"), str) and err["type"]
    assert isinstance(err.get("message"), str) and err["message"]


def test_rpc_payloads_are_json_strings_or_cloneable_not_deep_tojs() -> None:
    """Contract: edge uses json.dumps / structured clone — no deep toJs story."""
    mod = _load_rpc_module()
    # Prefer an explicit dumps helper if present; else exercise handle output.
    dumps = getattr(mod, "dumps_payload", None)
    if callable(dumps):
        sample = {"seq": 0, "episode_day": 0, "belief": {"L": 2, "K": 4}}
        out = dumps(sample)
        assert isinstance(out, str)
        json.loads(out)
    else:
        # Worker / RPC source must not instruct deep toJs of nested Python trees.
        sources: list[str] = []
        candidates = (
            _first_existing(_WORKER_CANDIDATES),
            _first_existing(_RPC_MODULE_CANDIDATES),
        )
        for path in candidates:
            if path is not None:
                sources.append(path.read_text(encoding="utf-8"))
        if not sources:
            pytest.fail("missing worker/RPC sources for toJs contract", pytrace=False)
        blob = "\n".join(sources)
        assert not re.search(r"toJs\s*\([^)]*depth\s*=\s*-?1", blob), (
            "must not deep toJs (depth=-1) nested EngineSession payloads"
        )
        assert re.search(r"json\.dumps|JSON\.stringify|structuredClone", blob), (
            "worker/RPC edge must serialise via json.dumps / JSON.stringify / "
            "structured clone (ADR 0098)"
        )


# ---------------------------------------------------------------------------
# AC: main thread only postMessage (no per-click runPython)
# ---------------------------------------------------------------------------


def test_main_thread_harness_postmessage_only_no_runpython() -> None:
    harness = _require_file(
        _MAIN_THREAD_HARNESS_CANDIDATES,
        what="main-thread smoke harness",
    )
    text = harness.read_text(encoding="utf-8")
    assert re.search(r"postMessage", text), (
        f"{_rel(harness)} must postMessage to the worker for engine calls"
    )
    # Allow comments mentioning the ban; disallow actual call sites.
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    stripped = re.sub(r"//.*?$", "", stripped, flags=re.M)
    assert not re.search(r"\brunPython\s*\(", stripped), (
        f"{_rel(harness)} must not call pyodide.runPython for per-click physics "
        "(worker-only Pyodide; ADR 0099)"
    )
    assert not re.search(r"\brunPythonAsync\s*\(", stripped), (
        f"{_rel(harness)} must not call runPythonAsync on the main thread"
    )


# ---------------------------------------------------------------------------
# AC: demo budget smoke (init + step + step_n ≥2) with dialed caps
# ---------------------------------------------------------------------------


def test_demo_budget_smoke_script_exists_with_pass_fail() -> None:
    smoke = _require_file(
        _SMOKE_SCRIPT_CANDIDATES,
        what="browser demo budget smoke script",
    )
    text = smoke.read_text(encoding="utf-8")
    assert re.search(r"init|step_n|DEMO_BUDGETS|demo", text, re.I), (
        f"{_rel(smoke)} must exercise demo budget init/step/step_n smoke"
    )
    # Documented exit contract or pytest-style assert; at least an exit code path.
    assert re.search(r"sys\.exit|exit\s+\d|raise SystemExit|process\.exit", text), (
        f"{_rel(smoke)} must have a clear pass/fail exit code path"
    )


def test_demo_budget_rpc_smoke_init_step_step_n_under_caps() -> None:
    """At least init + one step + step_n(≥2) under dialed DEMO_BUDGETS."""
    mod = _load_rpc_module()
    cfg = _demo_config()
    _assert_demo_budgets(cfg)
    assert int(cfg["n_particles"]) == int(DEMO_BUDGETS["n_particles"])
    assert int(cfg["n_particles"]) <= _DEMO_N_CAP

    wire_cfg = {k: v for k, v in cfg.items() if k != "shipments"}
    prepare = getattr(mod, "prepare_demo_config", None)
    if callable(prepare):
        wire_cfg = prepare(wire_cfg, shipments=_fixture_shipments())

    def call(method: str, params: dict[str, Any], *, req_id: str) -> Any:
        resp = _as_response(
            _rpc_handle(mod, {"id": req_id, "method": method, "params": params})
        )
        return _assert_ok_response(resp, req_id=req_id)

    snap = call("init", {"config": wire_cfg, "seed": 47}, req_id="smoke-init")
    assert isinstance(snap, Mapping)
    delta = call("step", {"order_qty": 1}, req_id="smoke-step")
    assert isinstance(delta, Mapping)
    multi = call("step_n", {"orders": [1, 2]}, req_id="smoke-stepn")
    if isinstance(multi, list):
        assert len(multi) >= 2
    elif isinstance(multi, Mapping) and "deltas" in multi:
        assert len(list(multi["deltas"])) >= 2
    else:
        pytest.fail("step_n smoke result must be list or {deltas: [...]}")


def test_rpc_rejects_or_documents_production_n_not_used_in_smoke() -> None:
    """Smoke path must not silently default to production N=2000."""
    smoke = _first_existing(_SMOKE_SCRIPT_CANDIDATES)
    rpc = _first_existing(_RPC_MODULE_CANDIDATES)
    chunks: list[str] = []
    if smoke is not None:
        chunks.append(smoke.read_text(encoding="utf-8"))
    if rpc is not None:
        chunks.append(rpc.read_text(encoding="utf-8"))
    worker = _first_existing(_WORKER_CANDIDATES)
    if worker is not None:
        chunks.append(worker.read_text(encoding="utf-8"))
    if not chunks:
        pytest.fail("missing smoke/RPC/worker to assert dialed budgets", pytrace=False)
    blob = "\n".join(chunks)
    # Must mention demo / DEMO_BUDGETS; must not set n_particles to 2000 for smoke.
    demo_pat = r"DEMO_BUDGETS|demo.?budget|n_particles.?<=?\s*200|\bN\s*<=?\s*200"
    assert re.search(demo_pat, blob, re.I), (
        "smoke/worker/RPC must dial demo budgets (≤200 particles), not production N"
    )
    assert not re.search(
        r"n_particles\s*[:=]\s*2000|N\s*[:=]\s*2000|PRODUCTION_N",
        blob,
    ), "smoke artifacts must not hard-code production N=2000"

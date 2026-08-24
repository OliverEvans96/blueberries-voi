"""T-125 migrated T-071: demo hydrate at WASM worker edge only.

Locks `.team/specs/T-125.md` AC-mixed: native ``EngineSession`` stays strict on
missing/empty shipments; browser demo hydrate lives in ``web/src/engine/wasmWorker.ts``
only — no ASGI FastAPI or ``packaging/pyodide/session_rpc.py`` paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from blueberries_voi.simulator.session import EngineSession

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WASM_WORKER = _REPO_ROOT / "web" / "src" / "engine" / "wasmWorker.ts"
_PYODIDE_RPC = _REPO_ROOT / "packaging" / "pyodide" / "session_rpc.py"
_PYODIDE_WORKER = _REPO_ROOT / "packaging" / "pyodide" / "worker.js"


def _wasm_worker_source() -> str:
    assert _WASM_WORKER.is_file(), (
        "web/src/engine/wasmWorker.ts must exist (sole browser RPC host per T-144)"
    )
    return _WASM_WORKER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-mixed: EngineSession stays strict (no demo hydrate inside session)
# ---------------------------------------------------------------------------


def test_engine_session_init_without_shipments_still_raises_value_error() -> None:
    with pytest.raises(ValueError, match=r"shipments"):
        EngineSession().init({})


def test_engine_session_init_with_empty_shipments_still_raises_value_error() -> None:
    with pytest.raises(ValueError, match=r"shipments"):
        EngineSession().init({"shipments": []})


# ---------------------------------------------------------------------------
# AC-mixed: WASM worker.js hydrates missing/empty shipments on init / reset
# ---------------------------------------------------------------------------


def test_wasm_worker_contains_ensure_demo_shipments_hydrate() -> None:
    demo_config = (_REPO_ROOT / "web" / "src" / "engine" / "demoConfig.ts").read_text(
        encoding="utf-8"
    )
    assert "ensureDemoShipments" in demo_config, (
        "demoConfig.ts must export ensureDemoShipments for demo hydrate (T-071 / T-125)"
    )
    text = _wasm_worker_source()
    assert "hydrateRpcRequest" in text or "demoConfig" in text, (
        "wasm worker must hydrate init/reset RPC before handle_rpc"
    )


def test_wasm_worker_uses_parquet_free_smoke_fixture() -> None:
    demo_config = (_REPO_ROOT / "web" / "src" / "engine" / "demoConfig.ts").read_text(
        encoding="utf-8"
    )
    assert "smokeCoolShipments" in demo_config, (
        "wasm demo hydrate must use parquet-free smoke fixture (ADR 0107)"
    )


def test_wasm_worker_hydrate_applies_on_init_and_reset() -> None:
    text = _wasm_worker_source()
    assert "hydrateRpcRequest" in text, (
        "wasm worker must hydrate init/reset RPC before handle_rpc"
    )
    demo_config = (_REPO_ROOT / "web" / "src" / "engine" / "demoConfig.ts").read_text(
        encoding="utf-8"
    )
    assert (
        "function hydrateRpcRequest" in demo_config
        or "export function hydrateRpcRequest" in demo_config
    )
    body = demo_config.split("hydrateRpcRequest", 1)[1][:600]
    assert "init" in body and "reset" in body, (
        "hydrateRpcRequest must handle init and reset methods"
    )


def test_wasm_worker_defers_shipments_when_arrival_product_set() -> None:
    """T-134/T-150: studio init must not force smokeCool when Rust can hydrate mod21."""
    demo_config = (_REPO_ROOT / "web" / "src" / "engine" / "demoConfig.ts").read_text(
        encoding="utf-8"
    )
    assert "arrival_product" in demo_config, (
        "demoConfig must recognize arrival_product for mod21 deferral"
    )
    assert "delete out.shipments" in demo_config or "mod21" in demo_config, (
        "demoConfig must leave shipments unset for Rust mod21_demo_shipments"
    )


# ---------------------------------------------------------------------------
# AC-pyodide / AC-mixed: retired Pyodide RPC paths absent (T-125)
# ---------------------------------------------------------------------------


def test_packaging_pyodide_session_rpc_absent() -> None:
    assert not _PYODIDE_RPC.is_file(), (
        "packaging/pyodide/session_rpc.py must be deleted (T-125 AC-pyodide); "
        "demo hydrate is wasm worker only"
    )


def test_packaging_pyodide_worker_absent() -> None:
    assert not _PYODIDE_WORKER.is_file(), (
        "packaging/pyodide/worker.js must be deleted (T-125 AC-pyodide); "
        "use web/src/engine/wasmWorker.ts only"
    )

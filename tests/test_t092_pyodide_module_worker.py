"""T-092 RED: Pyodide module-worker host (no classic importScripts).

Locks ``.team/specs/T-092.md`` and ADR 0111: under pin 314.0.4 the packaging
worker must ESM-import ``pyodide.mjs``, and hosts must spawn
``{ type: \"module\" }`` workers. Classic ``importScripts`` / ``pyodide.js`` /
``type: \"classic\"`` must fail these contracts.

Static / source contracts only — no live browser, no Playwright.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKER_JS = _REPO_ROOT / "packaging" / "pyodide" / "worker.js"
_MAIN_JS = _REPO_ROOT / "packaging" / "pyodide" / "main.js"
_ADAPTER_TS = _REPO_ROOT / "web" / "src" / "engine" / "pyodideAdapter.ts"
_WEB_PKG = _REPO_ROOT / "web" / "package.json"

_PYODIDE_PIN = "314.0.4"


def _strip_js_comments(src: str) -> str:
    no_block = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return re.sub(r"^\s*//.*$", "", no_block, flags=re.MULTILINE)


def test_worker_js_exists() -> None:
    assert _WORKER_JS.is_file(), f"missing packaging worker at {_WORKER_JS}"


def test_worker_bans_importscripts_and_classic_pyodide_js() -> None:
    """AC: no importScripts; no classic pyodide.js loader."""
    raw = _WORKER_JS.read_text(encoding="utf-8")
    src = _strip_js_comments(raw)
    assert "importScripts" not in src, (
        "worker.js must not call importScripts (classic workers rejected by "
        f"Pyodide {_PYODIDE_PIN}; ADR 0111)"
    )
    assert not re.search(r"pyodide\.js\b", src), (
        "worker.js must not load classic pyodide.js; use pyodide.mjs under "
        f"pin {_PYODIDE_PIN}"
    )


def test_worker_esm_imports_pyodide_mjs_under_pin() -> None:
    """AC: ESM import of …/pyodide/v314.0.4/full/pyodide.mjs (+ loadPyodide)."""
    raw = _WORKER_JS.read_text(encoding="utf-8")
    src = _strip_js_comments(raw)
    assert _PYODIDE_PIN in raw, f"worker.js must keep Pyodide pin {_PYODIDE_PIN}"
    assert re.search(r"pyodide\.mjs\b", src), (
        "worker.js must reference pyodide.mjs for ESM bootstrap"
    )
    assert re.search(
        rf"""from\s+["'][^"']*pyodide/v{_PYODIDE_PIN}/full/pyodide\.mjs["']""",
        src,
    ) or re.search(
        rf"""import\s*\(\s*["'][^"']*pyodide/v{_PYODIDE_PIN}/full/pyodide\.mjs["']""",
        src,
    ), (
        "worker.js must import loadPyodide from "
        f"…/pyodide/v{_PYODIDE_PIN}/full/pyodide.mjs"
    )
    assert re.search(r"\bloadPyodide\b", src), (
        "worker.js must call/import loadPyodide"
    )


def test_worker_retains_wheelurl_rpc_and_demo_budgets_hooks() -> None:
    """AC: wheelUrl / RPC / DEMO_BUDGETS contracts unchanged."""
    raw = _WORKER_JS.read_text(encoding="utf-8")
    src = _strip_js_comments(raw)
    assert "wheelUrl" in src
    for method in ("init", "step", "step_n", "reset", "act"):
        assert method in src, f"worker.js must retain RPC method {method!r}"
    assert "DEMO_BUDGETS" in src or "EngineSession" in src


def test_main_js_spawns_module_worker_not_classic() -> None:
    """AC: packaging/pyodide/main.js uses {{ type: \"module\" }}, not classic."""
    assert _MAIN_JS.is_file(), f"missing {_MAIN_JS}"
    src = _strip_js_comments(_MAIN_JS.read_text(encoding="utf-8"))
    assert re.search(
        r"""new\s+Worker\s*\([^)]*\{\s*type\s*:\s*["']module["']""",
        src,
    ), 'main.js must construct new Worker(..., { type: "module" })'
    assert not re.search(
        r"""type\s*:\s*["']classic["']""",
        src,
    ), 'main.js must not use { type: "classic" }'


def test_pyodide_adapter_spawns_module_worker() -> None:
    """AC: PyodideAdapter constructs new Worker(url, {{ type: \"module\" }})."""
    assert _ADAPTER_TS.is_file(), f"missing {_ADAPTER_TS}"
    src = _strip_js_comments(_ADAPTER_TS.read_text(encoding="utf-8"))
    assert re.search(
        r"""new\s+Worker\s*\([^)]*\{\s*type\s*:\s*["']module["']""",
        src,
    ), (
        'pyodideAdapter.ts must construct new Worker(url, { type: "module" }) '
        "(ADR 0111)"
    )
    assert not re.search(
        r"""type\s*:\s*["']classic["']""",
        src,
    ), "PyodideAdapter must not spawn a classic worker"


def test_no_new_playwright_dependency() -> None:
    """AC: do not add Playwright for this ticket."""
    assert _WEB_PKG.is_file(), f"missing {_WEB_PKG}"
    pkg = json.loads(_WEB_PKG.read_text(encoding="utf-8"))
    deps = {
        **(pkg.get("dependencies") or {}),
        **(pkg.get("devDependencies") or {}),
        **(pkg.get("optionalDependencies") or {}),
    }
    playwrightish = [
        name
        for name in deps
        if re.search(r"playwright|puppeteer", name, re.IGNORECASE)
    ]
    assert not playwrightish, (
        "T-092 must not add Playwright/Puppeteer; found: "
        + ", ".join(sorted(playwrightish))
    )

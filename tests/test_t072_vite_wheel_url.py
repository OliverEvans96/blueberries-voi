"""T-072 RED: Vite serves worker+wheel; packaging worker honors wheelUrl (ADR 0108).

Static / contract assertions only — no live Vite server, no production edits.
Fails until ``packaging/pyodide/worker.js`` reads ``?wheelUrl=`` (or configure /
init ``wheelUrl``) for micropip, and ``web/vite.config.ts`` exposes the documented
worker + local slim-wheel URLs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKER_JS = _REPO_ROOT / "packaging" / "pyodide" / "worker.js"
_VITE_CONFIG = _REPO_ROOT / "web" / "vite.config.ts"

_DOCUMENTED_WORKER_URL = "/packaging/pyodide/worker.js"
_LOCAL_WHEEL_URL_HINT = "/wheels/"


def _strip_js_comments(src: str) -> str:
    """Remove block + line comments so docs alone cannot satisfy contracts."""
    no_block = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return re.sub(r"^\s*//.*$", "", no_block, flags=re.MULTILINE)


def _strip_line_comments_only(src: str) -> str:
    """Strip ``//`` lines only — preserves Vite globs like ``src/**/*.test.ts``."""
    return re.sub(r"^\s*//.*$", "", src, flags=re.MULTILINE)


def test_worker_js_exists() -> None:
    assert _WORKER_JS.is_file(), f"missing packaging worker at {_WORKER_JS}"


def test_worker_js_honors_wheel_url_query_or_configure_for_micropip() -> None:
    """Acceptance: micropip.install uses ?wheelUrl= / configure|init wheelUrl when set.

    Hardcoded Release URL is fallback only (ADR 0108 / T-072).
    """
    raw = _WORKER_JS.read_text(encoding="utf-8")
    src = _strip_js_comments(raw)

    reads_query = bool(
        re.search(r"URLSearchParams|location\.search|self\.location", src)
    )
    mentions_wheel_url = "wheelUrl" in src
    accepts_configure_or_init_override = bool(
        re.search(
            r"""(?:configure|init)[\s\S]{0,400}wheelUrl|"""
            r"""wheelUrl[\s\S]{0,200}(?:configure|init|params)""",
            src,
        )
    )

    assert mentions_wheel_url, (
        "worker.js must reference wheelUrl (query and/or configure/init params) "
        "so a local override can reach micropip.install"
    )
    assert reads_query or accepts_configure_or_init_override, (
        "worker.js must read ?wheelUrl= via URLSearchParams / location.search "
        "and/or accept an explicit configure/init wheelUrl param (ADR 0108)"
    )

    install_args = re.findall(r"micropip\.install\s*\(\s*([^)]+?)\s*\)", src)
    assert install_args, "expected micropip.install(...) in worker.js"
    # Fallback-only: at least one install must not be the bare Release constant.
    non_constant = [
        arg
        for arg in install_args
        if arg.strip() not in {"SLIM_WHEEL_URL", "RELEASE_WHEEL_URL"}
    ]
    assert non_constant, (
        "micropip.install must use a resolved wheel URL (wheelUrl override when "
        "present); hardcoded SLIM_WHEEL_URL / Release URL is fallback only"
    )


def test_vite_config_serves_documented_worker_url() -> None:
    """Acceptance: Vite serves /packaging/pyodide/worker.js (or documented equivalent).

    Config must alias, middleware, publicDir, or fs.allow the packaging worker so
    a browser GET is HTTP 200, not 404 (implementer wires serve; this locks intent).
    """
    assert _VITE_CONFIG.is_file(), f"missing {_VITE_CONFIG}"
    cfg = _strip_line_comments_only(_VITE_CONFIG.read_text(encoding="utf-8"))

    mentions_packaging_worker = bool(
        re.search(
            r"packaging[/\\]pyodide|/packaging/pyodide/worker\.js|worker\.js",
            cfg,
        )
    )
    serve_mechanism = bool(
        re.search(
            r"""(?:alias|middleware|configureServer|publicDir|fs\s*:\s*\{[^}]*allow"""
            r"""|server\.fs\.allow|resolve\.alias)""",
            cfg,
        )
    )
    documents_worker_path = _DOCUMENTED_WORKER_URL in cfg or bool(
        re.search(r"packaging/pyodide", cfg)
    )

    assert documents_worker_path and mentions_packaging_worker and serve_mechanism, (
        "web/vite.config.ts must serve (alias / middleware / publicDir / fs.allow) "
        f"the packaging worker at {_DOCUMENTED_WORKER_URL} (or documented equivalent); "
        "current config has no packaging/pyodide serve wiring (T-072 / ADR 0108)"
    )


def test_vite_config_exposes_local_slim_wheel_path() -> None:
    """Acceptance: Vite exposes a local slim wheel URL (e.g. /wheels/*.whl)."""
    cfg = _strip_line_comments_only(_VITE_CONFIG.read_text(encoding="utf-8"))

    wheel_path_wired = bool(
        re.search(
            r"""/wheels/|['\"]wheels['\"]|"""
            r"""dist[/\\].*\.whl|\.whl|"""
            r"""build_slim_wheel""",
            cfg,
        )
    )
    # Also accept a Vite-visible public/wheels (or web/wheels) directory contract
    # once implementer lands it — but config or path must exist.
    public_wheels = (
        (_REPO_ROOT / "web" / "public" / "wheels").is_dir()
        or (_REPO_ROOT / "web" / "wheels").is_dir()
    )
    assert wheel_path_wired or public_wheels, (
        "Vite must expose a documented local slim-wheel URL (e.g. /wheels/*.whl "
        "or path from scripts/build_slim_wheel.py into a Vite-visible directory); "
        "web/vite.config.ts currently has no wheel serve wiring (T-072)"
    )


def test_vite_config_mentions_documented_local_urls_contract() -> None:
    """Config (or adjacent comment in the same file) pins worker + wheel URL shapes.

    Exact wheel static path under web/ may be finalize by implementer; the config
    must still acknowledge /wheels (or equivalent) and the packaging worker path.
    """
    cfg = _VITE_CONFIG.read_text(encoding="utf-8")
    has_worker_contract = bool(
        re.search(r"packaging/pyodide|/packaging/pyodide/worker", cfg)
    )
    has_wheel_contract = bool(re.search(r"/wheels/|wheels/\*\.whl|\.whl", cfg))
    assert has_worker_contract and has_wheel_contract, (
        "vite.config.ts should document/serve both the packaging worker URL and a "
        f"local wheel path (hint {_LOCAL_WHEEL_URL_HINT}*.whl) for dual-mode readiness"
    )


@pytest.mark.parametrize(
    "needle",
    (
        "wheelUrl",
        "VITE_PYODIDE_WHEEL_URL",
        "VITE_PYODIDE_WORKER_URL",
    ),
)
def test_studio_env_keys_remain_wheel_worker_contract(needle: str) -> None:
    """Studio contract keys stay VITE_PYODIDE_* (spec Interfaces); adapter must keep them."""
    studio = (_REPO_ROOT / "web" / "src" / "engine" / "studioAdapter.ts").read_text(
        encoding="utf-8"
    )
    assert needle in studio, (
        f"studioAdapter.ts must keep studio contract key {needle!r} (T-072)"
    )

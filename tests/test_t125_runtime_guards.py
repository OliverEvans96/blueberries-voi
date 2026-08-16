"""T-125 runtime guards — RED until Pyodide + HTTP paths are deleted (ADR 0129).

Locks AC-pyodide / AC-api / AC-closeout: retired packaging, Python modules, API
host, and frontend adapters must stay absent after implement shards land.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Directories and files that T-125 implement shards must delete.
_RETIRED_PATHS: tuple[Path, ...] = (
    _REPO_ROOT / "packaging" / "pyodide",
    _REPO_ROOT / "src" / "blueberries_voi" / "api",
    _REPO_ROOT / "src" / "blueberries_voi" / "browser.py",
    _REPO_ROOT / "src" / "blueberries_voi" / "slim_wheel_metadata.py",
    _REPO_ROOT / "scripts" / "build_slim_wheel.py",
    _REPO_ROOT / "scripts" / "smoke_slim_wheel.py",
    _REPO_ROOT / "scripts" / "smoke_pyodide_local_wheel.mjs",
    _REPO_ROOT / "experiments" / "bench_1d_90d_pyodide.mjs",
    _REPO_ROOT / "packaging" / "github-workflows" / "release-slim-wheel.yml",
    _REPO_ROOT / "web" / "src" / "engine" / "httpAdapter.ts",
    _REPO_ROOT / "web" / "src" / "engine" / "httpAdapter.test.ts",
    _REPO_ROOT / "web" / "src" / "engine" / "pyodideAdapter.ts",
    _REPO_ROOT / "web" / "src" / "engine" / "pyodideAdapter.test.ts",
    _REPO_ROOT / "web" / "src" / "engine" / "viteWheelUrl.test.ts",
    _REPO_ROOT / "tests" / "test_t047_pyodide_worker_rpc.py",
    _REPO_ROOT / "tests" / "test_t092_pyodide_module_worker.py",
    _REPO_ROOT / "tests" / "test_pyodide_slim_numpy_compat.py",
    _REPO_ROOT / "tests" / "test_t046_slim_wheel_release.py",
    _REPO_ROOT / "tests" / "test_t072_vite_wheel_url.py",
    _REPO_ROOT / "tests" / "test_t050_asgi_api.py",
    _REPO_ROOT / "tests" / "test_t051_api_contract.py",
    _REPO_ROOT / "tests" / "test_t073_api_cors.py",
)

_ENGINE_ADAPTER_FILES = (
    "httpAdapter.ts",
    "httpAdapter.test.ts",
    "pyodideAdapter.ts",
    "pyodideAdapter.test.ts",
)


def _rel(path: Path) -> str:
    return str(path.relative_to(_REPO_ROOT))


def _assert_absent(path: Path) -> None:
    assert not path.exists(), f"T-125 guard: retired path still present: {_rel(path)}"


@pytest.mark.parametrize(
    "retired_path",
    _RETIRED_PATHS,
    ids=[_rel(p) for p in _RETIRED_PATHS],
)
def test_retired_paths_absent(retired_path: Path) -> None:
    _assert_absent(retired_path)


def test_browser_and_slim_wheel_modules_not_importable() -> None:
    for module in ("blueberries_voi.browser", "blueberries_voi.slim_wheel_metadata"):
        spec = importlib.util.find_spec(module)
        assert spec is None, (
            f"T-125 guard: {module} is still importable (source file not removed)"
        )


def test_api_package_not_importable() -> None:
    spec = importlib.util.find_spec("blueberries_voi.api")
    assert spec is None, (
        "T-125 guard: blueberries_voi.api is still importable "
        "(src/blueberries_voi/api/ not removed)"
    )


def test_engine_dir_has_no_http_or_pyodide_adapter_files() -> None:
    engine = _REPO_ROOT / "web" / "src" / "engine"
    assert engine.is_dir(), f"missing engine directory: {_rel(engine)}"
    present = [name for name in _ENGINE_ADAPTER_FILES if (engine / name).is_file()]
    assert not present, (
        "T-125 guard: retired studio adapters still in web/src/engine: "
        + ", ".join(present)
    )


def test_studio_sh_is_wasm_only_no_mode_flags() -> None:
    """Launcher must not require --wasm; WASM is the only studio engine path."""
    text = (_REPO_ROOT / "scripts" / "studio.sh").read_text(encoding="utf-8")
    for flag in ("--wasm", "--http", "--pyodide"):
        assert flag not in text, (
            f"T-125 guard: studio.sh still mentions {flag}; launcher is WASM-only"
        )
    assert "VITE_ENGINE_ADAPTER=wasm" in text


def test_package_json_has_single_studio_script() -> None:
    pkg = (_REPO_ROOT / "web" / "package.json").read_text(encoding="utf-8")
    for script in ("studio:http", "studio:pyodide", "studio:wasm"):
        assert script not in pkg, (
            f"T-125 guard: web/package.json still defines {script}; use studio only"
        )
    assert "studio.sh" in pkg

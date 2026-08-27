"""CI workflow guards — python job reuses build artifacts."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CI_WORKFLOW = _REPO_ROOT / "packaging" / "github-workflows" / "ci.yml"
_CARGO_HELPERS = _REPO_ROOT / "tests" / "_cargo.py"


def _python_job_block(text: str) -> str:
    match = re.search(r"^  python:\n", text, flags=re.MULTILINE)
    assert match is not None, (
        "python job missing from packaging/github-workflows/ci.yml"
    )
    docs_match = re.search(r"^  docs:\n", text[match.start() :], flags=re.MULTILINE)
    assert docs_match is not None
    return text[match.start() : match.start() + docs_match.start()]


def test_python_job_reuses_build_wheel() -> None:
    """Python must download ci-rust-wasm-build and install the prebuilt PyO3 wheel."""
    python = _python_job_block(_CI_WORKFLOW.read_text(encoding="utf-8"))
    assert "needs: build" in python
    assert "name: ci-rust-wasm-build" in python
    assert "dist/wheels/blueberries_voi_core-" in python
    assert "unzip -oj" in python
    assert "blueberries_voi/_core.abi3.so" in python
    assert "maturin develop" not in python
    assert "maturin build" not in python
    assert "dtolnay/rust-toolchain" in python


def test_python_job_sync_skips_rust_extra() -> None:
    """Python install must not pull maturin/rust extra (wheel supplies _core)."""
    python = _python_job_block(_CI_WORKFLOW.read_text(encoding="utf-8"))
    assert "--all-extras" not in python
    assert "--extra rust" not in python
    assert "--extra dev" in python


def test_python_job_asserts_prebuilt_rust_artifacts() -> None:
    """Python must verify target/ reuse before pytest (no voi_* recompile)."""
    python = _python_job_block(_CI_WORKFLOW.read_text(encoding="utf-8"))
    assert "Verify prebuilt Rust artifacts" in python
    assert "Compiling (voi_core|voi_py|voi_wasm)" in python


def test_python_job_excludes_slow_pytest_marker() -> None:
    """PR/push python job must match local verify-fast pytest selection."""
    python = _python_job_block(_CI_WORKFLOW.read_text(encoding="utf-8"))
    assert '-m "not slow and not docs"' in python


def test_cargo_helpers_require_release_profile() -> None:
    """Centralized cargo helpers must always pass --release (no CI=true gate)."""
    assert _CARGO_HELPERS.is_file(), "tests/_cargo.py must exist"
    text = _CARGO_HELPERS.read_text(encoding="utf-8")
    assert "CARGO_RELEASE" in text
    assert '"--release"' in text
    assert "CI" not in text

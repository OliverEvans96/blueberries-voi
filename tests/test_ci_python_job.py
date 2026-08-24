"""CI workflow guards — python job reuses build artifacts."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CI_WORKFLOW = _REPO_ROOT / "packaging" / "github-workflows" / "ci.yml"


def _python_job_block(text: str) -> str:
    match = re.search(r"^  python:\n", text, flags=re.MULTILINE)
    assert match is not None, "python job missing from packaging/github-workflows/ci.yml"
    docs_match = re.search(r"^  docs:\n", text[match.start() :], flags=re.MULTILINE)
    assert docs_match is not None
    return text[match.start() : match.start() + docs_match.start()]


def test_python_job_reuses_build_wheel() -> None:
    """Python must download ci-rust-wasm-build and install the prebuilt PyO3 wheel."""
    python = _python_job_block(_CI_WORKFLOW.read_text(encoding="utf-8"))
    assert "needs: build" in python
    assert "name: ci-rust-wasm-build" in python
    assert "dist/wheels/blueberries_voi_core-" in python
    assert "maturin develop" not in python
    assert "dtolnay/rust-toolchain" not in python

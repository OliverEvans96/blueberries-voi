"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os

import pytest

F3_SUPERSESSION = "T-121 F3: ADR 0127 Wave F supersession"


@pytest.fixture(autouse=True)
def _wave_f_backend(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default rust backend for pytest; ``test_rust_*`` keeps rust."""
    node_path = str(getattr(request.node, "fspath", ""))
    if "test_rust_" in node_path or os.environ.get("BLUEBERRIES_VOI_BACKEND") is None:
        monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")

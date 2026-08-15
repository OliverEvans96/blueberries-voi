"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture(autouse=True)
def _python_backend_unless_rust_module(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy suite assumes Python compute unless a ``test_rust_*`` module overrides."""
    module_name = request.node.module.__name__
    if module_name.rsplit(".", 1)[-1].startswith("test_rust"):
        return
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "python")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)

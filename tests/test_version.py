"""Package metadata and CLI smoke tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueberries_voi import __version__
from blueberries_voi.__main__ import main

if TYPE_CHECKING:
    import pytest


def test_version_is_semver_shaped() -> None:
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_main_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "blueberries-voi" in captured.out

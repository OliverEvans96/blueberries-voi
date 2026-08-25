"""Rust kernel availability and PyO3 helper imports for doc figures."""

from __future__ import annotations

from typing import Any

from blueberries_voi.backend import rust_available, rust_core


def require_rust_core() -> Any:
    """Return ``blueberries_voi._core`` or raise if the extension is missing."""
    if not rust_available() or rust_core is None:
        raise RuntimeError(
            "doc figures require blueberries_voi._core; "
            "pip install -e '.[dev]' with a Rust toolchain"
        )
    return rust_core

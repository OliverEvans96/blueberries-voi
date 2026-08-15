"""Optional PyO3 kernel (`blueberries_voi._core`)."""

from __future__ import annotations

import importlib
import os
import warnings
from typing import Any

_WARNED = False
rust_core: Any | None
try:
    rust_core = importlib.import_module("blueberries_voi._core")
except ImportError:  # pragma: no cover - extension optional until maturin
    try:
        rust_core = importlib.import_module("_core")
    except ImportError:
        rust_core = None


def _backend() -> str:
    return os.environ.get("BLUEBERRIES_VOI_BACKEND", "rust").strip().lower()


def rust_available() -> bool:
    return rust_core is not None and _backend() == "rust"


def warn_fallback_once() -> None:
    global _WARNED
    if _backend() == "rust" and rust_core is None and not _WARNED:
        warnings.warn(
            "BLUEBERRIES_VOI_BACKEND=rust but blueberries_voi._core is missing; "
            "using Python",
            stacklevel=2,
        )
        _WARNED = True


__all__ = ["rust_available", "rust_core", "warn_fallback_once"]

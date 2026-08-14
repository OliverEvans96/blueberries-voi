"""Optional PyO3 kernel (`blueberries_voi._core`)."""

from __future__ import annotations

import os
import warnings

_BACKEND = os.environ.get("BLUEBERRIES_VOI_BACKEND", "python").strip().lower()
_WARNED = False

try:
    from blueberries_voi import _core as rust_core
except ImportError:  # pragma: no cover - extension optional until maturin
    rust_core = None


def rust_available() -> bool:
    return rust_core is not None and _BACKEND == "rust"


def warn_fallback_once() -> None:
    global _WARNED
    if _BACKEND == "rust" and rust_core is None and not _WARNED:
        warnings.warn(
            "BLUEBERRIES_VOI_BACKEND=rust but blueberries_voi._core is missing; using Python",
            stacklevel=2,
        )
        _WARNED = True

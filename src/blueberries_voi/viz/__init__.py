"""Visualization helpers for committed M1 / M1.5 figures."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

    fil11: ModuleType
    gate0: ModuleType
    m15: ModuleType
    voi: ModuleType

__all__ = ["fil11", "gate0", "m15", "voi"]


def __getattr__(name: str) -> object:
    if name in __all__:
        import importlib

        mod = importlib.import_module(f"blueberries_voi.viz.{name}")
        globals()[name] = mod
        return mod
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

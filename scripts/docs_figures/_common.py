"""Shared helpers for VitePress schematic figure scripts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _paths import OUT
from _style import apply_doc_style

if TYPE_CHECKING:
    from pathlib import Path


def setup_style() -> None:
    apply_doc_style()


def save_figure(name: str, out_dir: Path | None = None) -> Path:
    target = (out_dir or OUT) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(target, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close("all")
    return target

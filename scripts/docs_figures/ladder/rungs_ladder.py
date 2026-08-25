"""Schematic: seven knowledge rungs ladder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

RUNGS = [
    ("F3", "temp trace + GSIN + waste", "full cold-chain logger"),
    ("F2", "pack date + GSIN", "lot-resolved POS + supplier line"),
    ("F2a", "pack date + UPC", "pack-date on paperwork"),
    ("F1s", "GSIN + waste scan", "lot waste counts"),
    ("F1", "GSIN only", "lot-resolved POS"),
    ("P1", "UPC + waste", "handheld waste scanner"),
    ("P0", "books only", "POS totals + receiving log"),
]

COLORS = ["#2ca02c", "#8172b3", "#55a868", "#c44e52", "#dd8452", "#4c72b0", "#8c8c8c"]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, ax = plt.subplots(figsize=(8, 6))
    for i, ((name, triple, buy), color) in enumerate(zip(RUNGS, COLORS, strict=True)):
        y = len(RUNGS) - i
        ax.barh(y, 6, left=1.5, height=0.6, color=color, alpha=0.25, edgecolor=color)
        ax.text(0.2, y, name, fontweight="bold", fontsize=12, color=color)
        ax.text(4.5, y + 0.12, triple, ha="center", fontsize=8)
        ax.text(4.5, y - 0.15, buy, ha="center", fontsize=7, color="0.45")
    ax.set_xlim(0, 8)
    ax.set_ylim(0.5, len(RUNGS) + 0.5)
    ax.axis("off")
    ax.set_title("Seven named rungs — channel triple + what you'd buy", loc="left")
    fig.tight_layout()
    return save_figure("knowledge-rungs-ladder.png", out_dir)

"""Schematic: five-minutes day timeline with four panels."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

PANELS = [
    ("1 · Age", "shelf f decreases", "#4c72b0"),
    ("2 · Spoil", "dead units drop out", "#c44e52"),
    ("3 · Sell", "customers buy", "#55a868"),
    ("4 · Deliver", "new lot joins", "#8172b3"),
]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, axes = plt.subplots(1, 4, figsize=(10, 2.8))
    for ax, (title, note, color) in zip(axes, PANELS, strict=True):
        ax.add_patch(plt.Rectangle((0.1, 0.15), 0.8, 0.7, facecolor=color, alpha=0.2))
        for y, alpha in [(0.75, 1.0), (0.55, 0.7), (0.35, 0.45), (0.15, 0.2)]:
            ax.add_patch(plt.Circle((0.5, y), 0.08, color=color, alpha=alpha, ec="0.3"))
        ax.text(0.5, 0.92, title, ha="center", fontsize=10, fontweight="bold")
        ax.text(0.5, 0.05, note, ha="center", fontsize=7, color="0.4")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
    fig.suptitle("One simulated day (left → right)", y=1.02)
    fig.tight_layout()
    return save_figure("five-minutes-day-timeline.png", out_dir)

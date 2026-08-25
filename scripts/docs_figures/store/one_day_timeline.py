"""Schematic: one simulated day — Age, Spoil, Sell, Deliver."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

STEPS = [
    ("Age", "each unit's f decreases", "#4c72b0"),
    ("Spoil", "f ≤ 0 units removed", "#c44e52"),
    ("Sell", "demand draw + picking", "#55a868"),
    ("Deliver", "new lot joins shelf", "#8172b3"),
]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, ax = plt.subplots(figsize=(10, 2.5))
    n = len(STEPS)
    for i, (title, note, color) in enumerate(STEPS):
        x = i * 2.2
        ax.add_patch(
            plt.Rectangle(
                (x, 0.2), 1.8, 0.6, facecolor=color, alpha=0.25, edgecolor=color
            )
        )
        ax.text(x + 0.9, 0.65, title, ha="center", fontsize=12, fontweight="bold")
        ax.text(x + 0.9, 0.35, note, ha="center", fontsize=8, color="0.35")
        if i < n - 1:
            ax.annotate(
                "",
                xy=(x + 2.0, 0.5),
                xytext=(x + 1.8, 0.5),
                arrowprops={"arrowstyle": "->", "color": "0.4", "lw": 1.5},
            )
    ax.set_xlim(-0.2, n * 2.2)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("One simulated day (left → right)", loc="left", fontsize=11)
    fig.tight_layout()
    return save_figure("one-day-four-steps.png", out_dir)

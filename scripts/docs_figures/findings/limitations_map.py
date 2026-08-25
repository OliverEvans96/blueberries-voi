"""Schematic: limitations journey map."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

STAGES = [
    ("harvest", "out of scope", "#8c8c8c", 0.15),
    ("field heat", "out of scope", "#8c8c8c", 0.15),
    ("refrigerated leg", "modeled", "#4c72b0", 0.35),
    ("shelf life", "modeled", "#55a868", 0.35),
]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, ax = plt.subplots(figsize=(10, 2.5))
    for i, (name, scope, color, alpha) in enumerate(STAGES):
        x = i * 2.4
        ax.add_patch(
            plt.Rectangle((x, 0.2), 2.0, 0.6, facecolor=color, alpha=alpha, ec=color)
        )
        ax.text(x + 1.0, 0.55, name, ha="center", fontweight="bold")
        ax.text(x + 1.0, 0.35, scope, ha="center", fontsize=8, color="0.4")
        if i < len(STAGES) - 1:
            ax.annotate(
                "",
                xy=(x + 2.2, 0.5),
                xytext=(x + 2.0, 0.5),
                arrowprops={"arrowstyle": "->", "color": "0.4"},
            )
    ax.set_xlim(-0.2, 10)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("One delivery's journey — modeled vs out-of-scope", loc="left")
    fig.tight_layout()
    return save_figure("limitations-journey-map.png", out_dir)

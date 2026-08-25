"""Schematic: three run surfaces architecture."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

SURFACES = [
    ("Python package / CLI / notebooks", "pip wheel", "#4c72b0"),
    ("Rust voi_core crate", "native lib", "#8172b3"),
    ("Browser studio", ".wasm bundle", "#55a868"),
]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, ax = plt.subplots(figsize=(9, 4))
    for i, (name, artifact, color) in enumerate(SURFACES):
        y = len(SURFACES) - i
        ax.add_patch(
            plt.Rectangle(
                (0.5, y - 0.35), 6, 0.55, facecolor=color, alpha=0.2, ec=color
            )
        )
        ax.text(3.5, y + 0.05, name, ha="center", fontweight="bold")
        ax.text(7.2, y, f"← {artifact}", fontsize=10, color="0.45")
    ax.annotate(
        "shared physics kernel",
        xy=(3.5, 0.8),
        xytext=(3.5, 0.2),
        arrowprops={"arrowstyle": "<->", "color": "0.35"},
        ha="center",
        fontsize=9,
        color="0.45",
    )
    ax.set_xlim(0, 10)
    ax.set_ylim(0.5, len(SURFACES) + 0.5)
    ax.axis("off")
    ax.set_title("Three run surfaces — which artifact each consumes", loc="left")
    fig.tight_layout()
    return save_figure("run-surfaces-architecture.png", out_dir)

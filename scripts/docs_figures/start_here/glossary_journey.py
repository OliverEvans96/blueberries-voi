"""Schematic: symbol journey cheat sheet."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

STAGES = [
    ("corridor", "d, φ̄"),
    ("truck", "Λ"),
    ("shelf", "f"),
    ("sale", "ψ"),
]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, ax = plt.subplots(figsize=(10, 3))
    for i, (stage, sym) in enumerate(STAGES):
        x = i * 2.5
        ax.add_patch(
            plt.Rectangle(
                (x, 0.25), 2.0, 0.5, facecolor="#4c72b0", alpha=0.15, ec="#4c72b0"
            )
        )
        ax.text(x + 1.0, 0.55, stage, ha="center", fontsize=11, fontweight="bold")
        ax.text(x + 1.0, 0.38, sym, ha="center", fontsize=12, color="#2ca02c")
        if i < len(STAGES) - 1:
            ax.annotate(
                "",
                xy=(x + 2.3, 0.5),
                xytext=(x + 2.0, 0.5),
                arrowprops={"arrowstyle": "->", "color": "0.45", "lw": 1.5},
            )
    ax.set_xlim(-0.2, 10)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Where symbols live on a unit's journey", loc="left")
    fig.tight_layout()
    return save_figure("glossary-symbol-journey.png", out_dir)

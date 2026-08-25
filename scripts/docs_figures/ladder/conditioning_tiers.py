"""Schematic: conditioning tiers corridor → Λ."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

TIERS = [
    ("corridor", "route family"),
    ("duration d", "transit days"),
    ("φ̄", "mean temp factor"),
    ("Λ", "cumulative exposure"),
]
RUNG_MARKS = [("P0/P1", 1), ("F2/F2a", 2), ("F3", 4)]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, (label, sub) in enumerate(TIERS):
        y = len(TIERS) - i
        ax.add_patch(
            plt.Rectangle(
                (1, y - 0.35), 5, 0.55, facecolor="#4c72b0", alpha=0.12, ec="#4c72b0"
            )
        )
        ax.text(3.5, y, label, ha="center", fontsize=11, fontweight="bold")
        ax.text(3.5, y - 0.2, sub, ha="center", fontsize=8, color="0.45")
        if i < len(TIERS) - 1:
            ax.annotate(
                "",
                xy=(3.5, y - 0.45),
                xytext=(3.5, y - 0.35),
                arrowprops={"arrowstyle": "->", "color": "0.4"},
            )
    for name, tier in RUNG_MARKS:
        ax.text(6.3, tier, name, fontsize=9, color="#c44e52", fontweight="bold")
    ax.set_xlim(0, 8)
    ax.set_ylim(0.5, len(TIERS) + 0.5)
    ax.axis("off")
    ax.set_title("Conditioning hierarchy — no channel observes f directly", loc="left")
    fig.tight_layout()
    return save_figure("conditioning-tier-diagram.png", out_dir)

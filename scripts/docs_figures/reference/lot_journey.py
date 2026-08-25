"""Schematic: lot journey parameters diagram."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

MARKERS = [
    (0.15, "pack date"),
    (0.35, "d  transit duration"),
    (0.55, "T̄  mean transit temp"),
    (0.55, "φ̄  Q10 factor"),
    (0.75, "ψ  pallet position"),
    (0.90, "Λ  cumulative exposure"),
]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot([0.05, 0.95], [0.5, 0.5], color="#4c72b0", lw=3, solid_capstyle="round")
    ax.scatter([0.05, 0.95], [0.5, 0.5], s=80, color="#2ca02c", zorder=5)
    ax.text(0.05, 0.65, "pack", ha="center", fontsize=9)
    ax.text(0.95, 0.65, "store receipt", ha="center", fontsize=9)
    for x, label in MARKERS:
        ax.axvline(x, ymin=0.35, ymax=0.65, color="0.5", ls="--", lw=0.8)
        ax.text(x, 0.25, label, ha="center", fontsize=8, rotation=0)
    ax.text(
        0.5,
        0.82,
        "η_ref reference life (scale for exposures)",
        ha="center",
        fontsize=9,
        color="0.45",
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("One delivered lot — where each parameter applies", loc="left")
    fig.tight_layout()
    return save_figure("lot-journey-parameters.png", out_dir)

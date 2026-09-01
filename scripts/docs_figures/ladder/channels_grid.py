"""Schematic: observation channel grid presets."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

AXES = ("POS code", "waste scan", "delivery hist")
PRESETS = [
    ("P0", "UPC", "off", "qty only"),
    ("P1", "UPC", "on", "qty only"),
    ("F1", "LGTIN", "off", "qty only"),
    ("F1s", "LGTIN", "on", "qty only"),
    ("F2a", "UPC", "off", "pack date"),
    ("F2", "LGTIN", "off", "pack date"),
    ("F3", "LGTIN", "on", "temp trace"),
]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_xlim(0, 4)
    ax.set_ylim(0, len(PRESETS) + 1)
    ax.axis("off")
    ax.text(
        1.5,
        len(PRESETS) + 0.6,
        "Channel axes → named presets",
        fontsize=12,
        fontweight="bold",
    )
    for col, label in enumerate(AXES):
        ax.text(
            1.0 + col, len(PRESETS) + 0.2, label, ha="center", fontsize=9, color="0.4"
        )
    for row, (name, c, w, h) in enumerate(PRESETS):
        y = len(PRESETS) - row
        ax.text(0.2, y, name, fontweight="bold", fontsize=11, color="#4c72b0")
        for col, val in enumerate([c, w, h]):
            ax.add_patch(
                plt.Rectangle(
                    (0.7 + col, y - 0.35),
                    0.6,
                    0.5,
                    facecolor="#4c72b0",
                    alpha=0.12,
                    ec="0.3",
                )
            )
            ax.text(1.0 + col, y, val, ha="center", va="center", fontsize=8)
    fig.tight_layout()
    return save_figure("obs-channel-grid-presets.png", out_dir)

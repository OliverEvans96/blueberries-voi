"""Schematic: seven observation scenarios ladder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path

SCENARIOS = [
    (
        "Lot ID + pack date + temp history",
        "gsin + waste + temp trace",
        "cold-chain logger on pallet",
    ),
    (
        "Lot ID + pack date",
        "gsin + waste + pack date",
        "lot POS + supplier line",
    ),
    (
        "Pack date on ASN",
        "upc + waste + pack date",
        "pack date on paperwork",
    ),
    (
        "Lot ID on shrink gun",
        "gsin + waste (≡ lot at POS)",
        "lot waste counts only",
    ),
    ("Lot ID at POS", "gsin + waste", "lot-resolved checkout"),
    ("Shrink gun", "upc + waste", "handheld waste scanner"),
    ("Books only", "upc, no waste scan", "POS totals + receiving log"),
]

COLORS = ["#2ca02c", "#8172b3", "#55a868", "#c44e52", "#dd8452", "#4c72b0", "#8c8c8c"]


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, ax = plt.subplots(figsize=(9, 6))
    for i, ((name, triple, buy), color) in enumerate(
        zip(SCENARIOS, COLORS, strict=True)
    ):
        y = len(SCENARIOS) - i
        ax.barh(y, 6, left=1.5, height=0.6, color=color, alpha=0.25, edgecolor=color)
        ax.text(0.05, y, name, fontweight="bold", fontsize=9, color=color)
        ax.text(4.5, y + 0.12, triple, ha="center", fontsize=7)
        ax.text(4.5, y - 0.15, buy, ha="center", fontsize=6, color="0.45")
    ax.set_xlim(0, 8)
    ax.set_ylim(0.5, len(SCENARIOS) + 0.5)
    ax.axis("off")
    ax.set_title(
        "Seven observation scenarios — channel triple + what you'd buy",
        loc="left",
        fontsize=11,
    )
    fig.tight_layout()
    return save_figure("observation-scenarios-ladder.png", out_dir)

"""Schematic: particle shelf shading across particles."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path


def _draw_shelf(
    ax: plt.Axes, widths: list[int], f_vals: list[float], title: str
) -> None:
    x = 0.0
    for w, f in zip(widths, f_vals, strict=True):
        color = plt.cm.RdYlGn(f)
        ax.add_patch(plt.Rectangle((x, 0.1), w, 0.8, facecolor=color, ec="0.3"))
        ax.text(x + w / 2, 0.5, f"{w}", ha="center", va="center", fontsize=8)
        x += w
    ax.set_xlim(0, x)
    ax.set_ylim(0, 1)
    ax.set_title(title, fontsize=9)
    ax.axis("off")


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    widths = [15, 9]
    fig, axes = plt.subplots(1, 3, figsize=(10, 2.5))
    rng = np.random.default_rng(3)
    for i, ax in enumerate(axes):
        f_vals = [rng.uniform(0.3, 0.95), rng.uniform(0.2, 0.9)]
        _draw_shelf(ax, widths, f_vals, f"particle {i + 1}")
    fig.suptitle("Same lot widths — freshness shading varies per particle", y=1.05)
    fig.tight_layout()
    return save_figure("particle-shelf-shading.png", out_dir)

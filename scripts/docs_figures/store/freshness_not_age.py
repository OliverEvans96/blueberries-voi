"""Schematic: freshness vs calendar age."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from _common import save_figure, setup_style

if TYPE_CHECKING:
    from pathlib import Path


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))

    ax = axes[0]
    ax.set_title("Same calendar age, different freshness")
    for f_val, label, color in [
        (0.85, "Unit A  f = 0.85", "#2ca02c"),
        (0.45, "Unit B  f = 0.45", "#dd8452"),
    ]:
        ax.barh(label, 14, color=color, alpha=0.35, height=0.5)
        ax.text(7, label, f"{f_val:.2f}", ha="center", va="center", fontsize=11)
    ax.set_xlim(0, 14)
    ax.set_xlabel("calendar days since pack")
    ax.set_yticks([])

    ax2 = axes[1]
    days = np.arange(0, 15)
    f_path = np.clip(1.0 - 0.07 * days - 0.02 * days**2, 0, 1)
    ax2.plot(days, f_path, "o-", color="#4c72b0", lw=2)
    ax2.axhline(0, color="0.5", ls="--", lw=1)
    ax2.set_xlabel("calendar day")
    ax2.set_ylabel("freshness  f")
    ax2.set_ylim(-0.05, 1.05)
    ax2.set_title("f drains toward 0 while days tick evenly")

    fig.tight_layout()
    return save_figure("freshness-not-age-schematic.png", out_dir)

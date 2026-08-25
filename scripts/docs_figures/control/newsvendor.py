"""Schematic: newsvendor critical fractile shading."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from _common import save_figure, setup_style
from scipy.stats import norm

if TYPE_CHECKING:
    from pathlib import Path


def render(out_dir: Path | None = None) -> Path:
    setup_style()
    mu, sigma = 10.0, 3.0
    q = 11.5
    x = np.linspace(mu - 4 * sigma, mu + 4 * sigma, 400)
    y = norm.pdf(x, mu, sigma)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x, y, color="#4c72b0", lw=2)
    ax.fill_between(
        x, y, where=x <= q, alpha=0.35, color="#55a868", label="overage (q too high)"
    )
    ax.fill_between(
        x, y, where=x > q, alpha=0.35, color="#c44e52", label="underage (q too low)"
    )
    ax.axvline(q, color="0.2", ls="--", lw=1.5)
    ax.text(q + 0.2, max(y) * 0.9, "order q", fontsize=10)
    ax.set_xlabel("demand")
    ax.set_ylabel("probability")
    ax.set_title("Tilting q trades overage area for underage area")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    return save_figure("newsvendor-critical-fractile.png", out_dir)

"""Rust-backed: birth freshness CDF by rung family via arrival_marginal_cdf_py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from _paths import OUT, REPO
from _rust import require_rust_core
from _style import apply_doc_style, save_fig

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT = "birth-freshness-cdf-by-rung-family.png"
ARTIFACT = REPO / "data" / "abdella" / "arrival_model.json"


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    core = require_rust_core()
    target = (out_dir or OUT) / OUTPUT

    f_grid = list(np.linspace(0.0, 1.0, 81))
    source = str(ARTIFACT)
    panels = (
        ("P0 · P1", "prior", "#8c8c8c"),
        ("F2 · F2a", "duration:5", "#55a868"),
        ("F3", "exposure:2.5", "#2ca02c"),
    )

    fig, axes = plt.subplots(1, 3, figsize=(9, 3.5), sharey=True)
    for ax, (title, condition, color) in zip(axes, panels, strict=True):
        cdf = np.asarray(
            core.arrival_marginal_cdf_py(source, condition, f_grid),
            dtype=float,
        )
        ax.plot(f_grid, cdf, color=color, lw=2)
        ax.scatter([0.0], [cdf[0]], color=color, s=36, zorder=5)
        ax.text(0.05, min(0.95, cdf[0] + 0.08), "f=0 atom", fontsize=7, color="0.45")
        ax.set_xlabel("birth freshness  f")
        ax.set_title(title)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.05)
    axes[0].set_ylabel("arrival CDF")
    fig.suptitle("arrival_marginal_cdf_py — conditioning narrows the law", y=1.02)
    save_fig(target)
    return target

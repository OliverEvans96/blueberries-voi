"""Shared matplotlib styling for documentation figures."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import matplotlib.pyplot as plt

DEFAULT_DPI = 120


def apply_doc_style() -> None:
    """Apply rcParams tuned for VitePress-embedded figures."""
    plt.rcParams.update(
        {
            "figure.figsize": (6.0, 3.5),
            "figure.dpi": DEFAULT_DPI,
            "savefig.dpi": DEFAULT_DPI,
            "font.size": 10,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "lines.linewidth": 1.5,
        }
    )


def save_fig(path: Path, *, tight: bool = True) -> None:
    """Save the current figure to ``path`` at doc-figure DPI."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if tight:
        plt.tight_layout()
    plt.savefig(path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close()

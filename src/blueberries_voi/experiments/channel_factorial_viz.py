"""Facet heatmaps and tradeoff plots for nb19 channel-joint rows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

if TYPE_CHECKING:
    from pathlib import Path

    from matplotlib.figure import Figure

from blueberries_voi.experiments.channel_joint import (
    CODE_OPTS,
    DELIVERY_OPTS,
    WASTE_OPTS,
)

AccuracyColumn = Literal["mae_f", "mae_dist"]

__all__ = [
    "AccuracyColumn",
    "facet_heatmap_figure",
    "parallel_coords_figure",
    "profit_vs_accuracy_scatter_figure",
    "rows_to_dataframe",
    "save_nb19_figures",
]


def rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Normalize shard/merge rows for plotting."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ("mae_f", "mae_dist", "profit"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def facet_heatmap_figure(
    df: pd.DataFrame,
    *,
    accuracy_column: AccuracyColumn = "mae_f",
    figsize: tuple[float, float] = (12, 4.5),
) -> Figure:
    """Facet heatmaps: one panel per delivery history (code x waste cells)."""
    fig, axes = plt.subplots(
        1,
        len(DELIVERY_OPTS),
        figsize=figsize,
        sharey=True,
        constrained_layout=True,
    )
    vmin = float(df[accuracy_column].min())
    vmax = float(df[accuracy_column].max())
    im = None
    for ax, delivery in zip(axes, DELIVERY_OPTS, strict=True):
        sub = df[df["delivery"] == delivery]
        grid = np.full((len(CODE_OPTS), len(WASTE_OPTS)), np.nan)
        for i, code in enumerate(CODE_OPTS):
            for j, waste in enumerate(WASTE_OPTS):
                hit = sub[(sub["code_type"] == code) & (sub["waste"] == waste)]
                if len(hit):
                    grid[i, j] = float(hit[accuracy_column].mean())
        im = ax.imshow(grid, cmap="RdYlGn_r", vmin=vmin, vmax=vmax)
        ax.set_xticks(range(len(WASTE_OPTS)), WASTE_OPTS, rotation=25, ha="right")
        ax.set_yticks(range(len(CODE_OPTS)), CODE_OPTS)
        ax.set_title(f"delivery={delivery}")
        for i in range(len(CODE_OPTS)):
            for j in range(len(WASTE_OPTS)):
                val = grid[i, j]
                if np.isfinite(val):
                    ax.text(j, i, f"{val:.3f}", ha="center", va="center", fontsize=8)
    label = "MAE(mean f)" if accuracy_column == "mae_f" else "MAE(distribution)"
    if im is not None:
        fig.colorbar(
            im,
            ax=axes,
            location="right",
            shrink=0.92,
            pad=0.02,
            label=label,
        )
    fig.suptitle(f"Channel factorial · {label}")
    return fig


def profit_vs_accuracy_scatter_figure(
    df: pd.DataFrame,
    *,
    accuracy_column: AccuracyColumn = "mae_f",
    figsize: tuple[float, float] = (10.0, 4.8),
) -> Figure:
    """Scatter profit vs belief accuracy faceted by code type.

    Color encodes waste scan (on/off); marker shape encodes delivery history.
    """
    waste_colors = {"off": "#4c72b0", "on": "#dd8452"}
    delivery_markers = {
        "none": "o",
        "pack_date": "s",
        "temperature_history": "^",
    }
    fig, axes = plt.subplots(
        1,
        len(CODE_OPTS),
        figsize=figsize,
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )
    xlabel = "MAE(mean f)" if accuracy_column == "mae_f" else "MAE(distribution)"
    for ax, code in zip(axes, CODE_OPTS, strict=True):
        sub = df[df["code_type"] == code]
        for waste in WASTE_OPTS:
            for delivery in DELIVERY_OPTS:
                pts = sub[(sub["waste"] == waste) & (sub["delivery"] == delivery)]
                if pts.empty:
                    continue
                ax.scatter(
                    pts[accuracy_column],
                    pts["profit"],
                    color=waste_colors[waste],
                    marker=delivery_markers[delivery],
                    alpha=0.85,
                    s=70,
                    edgecolor="0.2",
                )
        ax.set_title(f"code={code}")
        ax.set_xlabel(xlabel)
    axes[0].set_ylabel("Closed-loop profit")

    waste_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=waste_colors[waste],
            markeredgecolor="0.2",
            markersize=8,
            label=f"waste scan {waste}",
        )
        for waste in WASTE_OPTS
    ]
    delivery_handles = [
        Line2D(
            [0],
            [0],
            marker=delivery_markers[delivery],
            color="0.35",
            linestyle="None",
            markersize=8,
            label=delivery,
        )
        for delivery in DELIVERY_OPTS
    ]
    fig.legend(
        handles=waste_handles + delivery_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.08),
        ncol=5,
        frameon=False,
        title="color = waste scan · marker = delivery history · facet = code type",
    )
    fig.suptitle("Belief accuracy vs profit (nb19)", y=1.14)
    return fig


def parallel_coords_figure(
    df: pd.DataFrame,
    *,
    accuracy_column: AccuracyColumn = "mae_f",
    figsize: tuple[float, float] = (8.0, 5.0),
) -> Figure:
    """Parallel coordinates over code, waste, delivery, accuracy, profit."""
    fig, ax = plt.subplots(figsize=figsize)
    if df.empty:
        return fig

    code_map = {c: i for i, c in enumerate(CODE_OPTS)}
    waste_map = {w: i for i, w in enumerate(WASTE_OPTS)}
    del_map = {d: i for i, d in enumerate(DELIVERY_OPTS)}

    acc = df[accuracy_column].astype(float)
    prof = df["profit"].astype(float)
    acc_norm = (acc - acc.min()) / max(acc.max() - acc.min(), 1e-9)
    prof_norm = (prof - prof.min()) / max(prof.max() - prof.min(), 1e-9)

    xs = [0, 1, 2, 3, 4]
    xticks = ["code", "waste", "delivery", accuracy_column, "profit"]

    for row, a_n, p_n in zip(df.itertuples(), acc_norm, prof_norm, strict=True):
        ys = [
            float(code_map.get(row.code_type, 0)),
            float(waste_map.get(row.waste, 0)),
            float(del_map.get(row.delivery, 0)),
            float(a_n),
            float(p_n),
        ]
        ax.plot(xs, ys, color="0.55", alpha=0.35, lw=1)

    ax.set_xticks(xs, xticks, rotation=20, ha="right")
    ax.set_ylabel("normalized / ordinal")
    ax.set_title("Channel paths (normalized accuracy + profit)")
    fig.tight_layout()
    return fig


def save_nb19_figures(
    rows: list[dict[str, Any]],
    out_dir: Path,
    *,
    accuracy_column: AccuracyColumn = "mae_f",
) -> list[Path]:
    """Write standard nb19 figure set to ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    df = rows_to_dataframe(rows)
    written: list[Path] = []

    fig = facet_heatmap_figure(df, accuracy_column=accuracy_column)
    path = out_dir / f"channel_factorial_heatmap_{accuracy_column}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    fig = profit_vs_accuracy_scatter_figure(df, accuracy_column=accuracy_column)
    path = out_dir / f"profit_vs_{accuracy_column}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    fig = parallel_coords_figure(df, accuracy_column=accuracy_column)
    path = out_dir / f"parallel_coords_{accuracy_column}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    written.append(path)

    return written

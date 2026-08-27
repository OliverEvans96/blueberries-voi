"""Smoke tests for nb19 channel factorial visualizations."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from blueberries_voi.experiments.channel_factorial_viz import (
    CODE_TYPE_LABELS,
    DELIVERY_LABELS,
    WASTE_LABELS,
    aggregate_factorial_cells,
    facet_heatmap_figure,
    parallel_coords_figure,
    profit_vs_accuracy_scatter_figure,
    rows_to_dataframe,
    save_nb19_figures,
)

SAMPLE_ROWS = [
    {
        "seed": 42,
        "key": "code=upc|waste=0|hist=none",
        "code_type": "upc",
        "waste": "off",
        "delivery": "none",
        "mae_f": 0.12,
        "mae_dist": 0.08,
        "profit": 10.5,
        "preset": "P0",
    },
    {
        "seed": 42,
        "key": "code=gsin|waste=1|hist=temperature_history",
        "code_type": "gsin",
        "waste": "on",
        "delivery": "temperature_history",
        "mae_f": 0.09,
        "mae_dist": 0.05,
        "profit": 12.1,
        "preset": "F3",
    },
]


MULTI_SEED_ROWS = [
    {
        "seed": 7,
        "code_type": "upc",
        "waste": "off",
        "delivery": "none",
        "mae_f": 0.10,
        "mae_dist": 0.06,
        "profit": 10.0,
    },
    {
        "seed": 42,
        "code_type": "upc",
        "waste": "off",
        "delivery": "none",
        "mae_f": 0.12,
        "mae_dist": 0.08,
        "profit": 10.5,
    },
    {
        "seed": 99,
        "code_type": "upc",
        "waste": "off",
        "delivery": "none",
        "mae_f": 0.14,
        "mae_dist": 0.10,
        "profit": 11.0,
    },
    {
        "seed": 7,
        "code_type": "gsin",
        "waste": "on",
        "delivery": "temperature_history",
        "mae_f": 0.08,
        "mae_dist": 0.04,
        "profit": 11.8,
    },
    {
        "seed": 42,
        "code_type": "gsin",
        "waste": "on",
        "delivery": "temperature_history",
        "mae_f": 0.09,
        "mae_dist": 0.05,
        "profit": 12.1,
    },
    {
        "seed": 99,
        "code_type": "gsin",
        "waste": "on",
        "delivery": "temperature_history",
        "mae_f": 0.10,
        "mae_dist": 0.06,
        "profit": 12.4,
    },
]


def test_rows_to_dataframe_numeric() -> None:
    df = rows_to_dataframe(SAMPLE_ROWS)
    assert float(df["profit"].iloc[0]) == 10.5


def test_aggregate_factorial_cells_reduces_multi_seed_rows() -> None:
    df = rows_to_dataframe(MULTI_SEED_ROWS)
    agg = aggregate_factorial_cells(df, accuracy_column="mae_f")
    assert len(agg) == 2
    assert len(agg) < len(df)
    upc = agg[agg["code_type"] == "upc"].iloc[0]
    assert float(upc["mae_mean"]) == 0.12
    assert float(upc["profit_mean"]) == 10.5
    assert float(upc["mae_std"]) > 0.0
    assert float(upc["profit_std"]) > 0.0


def test_scatter_aggregates_multi_seed_with_errorbars() -> None:
    df = rows_to_dataframe(MULTI_SEED_ROWS)
    fig = profit_vs_accuracy_scatter_figure(df, accuracy_column="mae_f")
    ax = fig.axes[0]
    assert len(ax.containers) == 2
    assert len(ax.containers) < len(df)


def test_facet_heatmap_figure_builds() -> None:
    df = rows_to_dataframe(SAMPLE_ROWS)
    fig = facet_heatmap_figure(df, accuracy_column="mae_f")
    assert fig.axes


def test_scatter_and_parallel_build() -> None:
    df = rows_to_dataframe(SAMPLE_ROWS)
    fig1 = profit_vs_accuracy_scatter_figure(df, accuracy_column="mae_dist")
    fig2 = parallel_coords_figure(df, accuracy_column="mae_f")
    assert len(fig1.axes) == 1
    assert fig2.axes


def test_scatter_legend_encodes_waste_delivery_and_code_type() -> None:
    df = rows_to_dataframe(SAMPLE_ROWS)
    fig = profit_vs_accuracy_scatter_figure(df, accuracy_column="mae_f")
    assert len(fig.legends) == 3
    legend_titles = {legend.get_title().get_text() for legend in fig.legends}
    assert legend_titles == {
        "Waste scan (color)",
        "Delivery history (marker)",
        "Code type (marker size)",
    }
    labels = {text.get_text() for legend in fig.legends for text in legend.get_texts()}
    assert WASTE_LABELS["off"] in labels
    assert WASTE_LABELS["on"] in labels
    assert DELIVERY_LABELS["none"] in labels
    assert DELIVERY_LABELS["pack_date"] in labels
    assert DELIVERY_LABELS["temperature_history"] in labels
    assert CODE_TYPE_LABELS["upc"] in labels
    assert CODE_TYPE_LABELS["gsin"] in labels
    assert fig._suptitle is None
    assert fig.axes[0].get_title() == "Belief accuracy vs profit (nb19)"


def test_save_nb19_figures_writes_files(tmp_path: Path) -> None:
    paths = save_nb19_figures(SAMPLE_ROWS, tmp_path, accuracy_column="mae_f")
    assert paths
    assert all(p.is_file() for p in paths)

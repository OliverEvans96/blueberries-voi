"""Smoke tests for nb19 channel factorial visualizations."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from blueberries_voi.experiments.channel_factorial_viz import (
    DELIVERY_LABELS,
    WASTE_LABELS,
    facet_heatmap_figure,
    parallel_coords_figure,
    profit_vs_accuracy_scatter_figure,
    rows_to_dataframe,
    save_nb19_figures,
)
from blueberries_voi.experiments.channel_joint import CODE_OPTS

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


def test_rows_to_dataframe_numeric() -> None:
    df = rows_to_dataframe(SAMPLE_ROWS)
    assert float(df["profit"].iloc[0]) == 10.5


def test_facet_heatmap_figure_builds() -> None:
    df = rows_to_dataframe(SAMPLE_ROWS)
    fig = facet_heatmap_figure(df, accuracy_column="mae_f")
    assert fig.axes


def test_scatter_and_parallel_build() -> None:
    df = rows_to_dataframe(SAMPLE_ROWS)
    fig1 = profit_vs_accuracy_scatter_figure(df, accuracy_column="mae_dist")
    fig2 = parallel_coords_figure(df, accuracy_column="mae_f")
    assert len(fig1.axes) == len(CODE_OPTS)
    assert fig2.axes


def test_scatter_legend_encodes_waste_and_delivery() -> None:
    df = rows_to_dataframe(SAMPLE_ROWS)
    fig = profit_vs_accuracy_scatter_figure(df, accuracy_column="mae_f")
    assert len(fig.legends) == 2
    legend_titles = {legend.get_title().get_text() for legend in fig.legends}
    assert legend_titles == {
        "Waste scan (color)",
        "Delivery history (marker)",
    }
    labels = {
        text.get_text() for legend in fig.legends for text in legend.get_texts()
    }
    assert WASTE_LABELS["off"] in labels
    assert WASTE_LABELS["on"] in labels
    assert DELIVERY_LABELS["none"] in labels
    assert DELIVERY_LABELS["pack_date"] in labels
    assert DELIVERY_LABELS["temperature_history"] in labels


def test_scatter_panel_titles_encode_code_type() -> None:
    df = rows_to_dataframe(SAMPLE_ROWS)
    fig = profit_vs_accuracy_scatter_figure(df, accuracy_column="mae_f")
    panel_titles = {ax.get_title() for ax in fig.axes}
    assert panel_titles == {"UPC barcode", "GSIN case code"}
    assert "Panels separate code type" in fig._suptitle.get_text()


def test_save_nb19_figures_writes_files(tmp_path: Path) -> None:
    paths = save_nb19_figures(SAMPLE_ROWS, tmp_path, accuracy_column="mae_f")
    assert paths
    assert all(p.is_file() for p in paths)

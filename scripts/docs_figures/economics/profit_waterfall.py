"""Rust-backed: one-day profit waterfall P0 vs F2 from EngineSession."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _paths import OUT
from _rust import require_rust_core
from _style import apply_doc_style, save_fig

from blueberries_voi.sim.profit import DEFAULT_PROFIT_COSTS
from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.simulator.session import EngineSession

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT = "profit-waterfall-daily.png"


def _day_components(day: dict[str, object]) -> tuple[float, float, float, float]:
    costs = DEFAULT_PROFIT_COSTS
    sales = int(day.get("sales_total", day.get("sales", 0)))
    waste = int(day.get("waste_total", day.get("waste", 0)))
    demand = int(day.get("demand", 0))
    lost = max(0, demand - sales)
    margin = costs.unit_margin * sales
    waste_cost = -costs.waste_cost * waste
    stockout = -costs.stockout_penalty * lost
    net = margin + waste_cost + stockout
    return margin, waste_cost, stockout, net


def _one_scenario_day(
    scenario: str, seed: int = 11
) -> tuple[float, float, float, float]:
    session = EngineSession()
    session.init(
        {
            "shipments": smoke_cool_shipments(),
            "obs_scenario": scenario,
            "enable_filter": True,
            "L": 6,
            "K": 4,
        },
        seed=seed,
    )
    for _ in range(3):
        session.step(64)
    delta = session.act(policy="sw", alpha=0.9)
    day_raw = delta.get("day") if isinstance(delta.get("day"), dict) else delta
    return _day_components(day_raw if isinstance(day_raw, dict) else {})


def _waterfall(
    ax: plt.Axes, values: tuple[float, float, float, float], title: str
) -> None:
    labels = ["margin", "waste", "stockout", "net"]
    colors = ["#55a868", "#c44e52", "#dd8452", "#2563eb"]
    cumulative = 0.0
    for i, (lab, val) in enumerate(zip(labels, values, strict=True)):
        bottom = 0.0 if lab == "net" else cumulative
        height = val
        if lab == "net":
            ax.bar(i, height, color=colors[i], edgecolor="0.2")
        else:
            ax.bar(i, val, bottom=bottom, color=colors[i], edgecolor="0.2")
            cumulative += val
        ax.text(
            i,
            height + (5 if height >= 0 else -15),
            f"{height:.0f}",
            ha="center",
            fontsize=8,
        )
    ax.axhline(0, color="0.3", lw=0.8)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_title(title)


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    require_rust_core()
    target = (out_dir or OUT) / OUTPUT

    p0 = _one_scenario_day("P0")
    f2 = _one_scenario_day("F2", seed=12)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True)
    _waterfall(axes[0], p0, "P0 (books only)")
    _waterfall(axes[1], f2, "F2 (pack date)")
    axes[0].set_ylabel("profit ($)")
    fig.suptitle("One scored day — DEFAULT_PROFIT_COSTS components", y=1.02)
    save_fig(target)
    return target

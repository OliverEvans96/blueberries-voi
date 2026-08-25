"""Rust-backed: OrderSchedule.protection_days on Sun/Tue/Thu order days."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _paths import OUT
from _style import apply_doc_style, save_fig

from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT = "protection-window-calendar.png"
_EPOCH = date(2024, 1, 1)


def _weekday_label(day_index: int) -> str:
    return (_EPOCH + timedelta(days=day_index)).strftime("%a")


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    target = (out_dir or OUT) / OUTPUT
    schedule = DEFAULT_ORDER_SCHEDULE

    order_days = sorted(schedule.order_weekdays)
    labels = [_weekday_label(d) for d in order_days]
    windows = [schedule.protection_days(d) for d in order_days]

    _fig, ax = plt.subplots(figsize=(7, 4))
    colors = ["#dd8452" if w >= 4 else "#2563eb" for w in windows]
    ax.bar(labels, windows, color=colors, edgecolor="0.2", linewidth=0.6)
    ax.set_ylabel("protection window (days)")
    ax.set_title("MWF delivery — 3 / 3 / 4 on Sun / Tue / Thu orders")
    save_fig(target)
    return target

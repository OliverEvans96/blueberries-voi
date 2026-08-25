"""Rust-backed: demand_profile_mu_py over 91 days from FreshNet profile."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from _paths import OUT, REPO
from _rust import require_rust_core
from _style import apply_doc_style, save_fig

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT = "demand-calendar-sawtooth.png"
PROFILE = REPO / "data" / "freshnet" / "demand_profile.json"


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    core = require_rust_core()
    target = (out_dir or OUT) / OUTPUT

    profile_path = str(PROFILE)
    days = np.arange(91)
    mu = np.asarray(
        [core.demand_profile_mu_py(int(d), profile_path) for d in days],
        dtype=float,
    )

    _fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.bar(days, mu, width=1.0, color="#2563eb", alpha=0.8, edgecolor="none")
    ax.set_xlabel("day (13-week window)")
    ax.set_ylabel("μ(day)")
    ax.set_title("FreshNet demand profile via demand_profile_mu_py")
    save_fig(target)
    return target

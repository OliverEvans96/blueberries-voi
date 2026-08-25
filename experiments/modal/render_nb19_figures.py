"""Regenerate notebook 19 figures from ``nb19_joint_rows.json``."""

from __future__ import annotations

import json
from pathlib import Path

from blueberries_voi.experiments.channel_factorial_viz import save_nb19_figures

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "experiments" / "data"
FIG_DIR = REPO / "figures" / "channel_joint"


def main() -> None:
    rows_path = DATA / "nb19_joint_rows.json"
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    written = save_nb19_figures(rows, FIG_DIR, accuracy_column="mae_f")
    written.extend(save_nb19_figures(rows, FIG_DIR, accuracy_column="mae_dist"))
    for path in written:
        print("wrote", path.relative_to(REPO))


if __name__ == "__main__":
    main()

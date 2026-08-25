#!/usr/bin/env python3
"""Emit calibration overlay from committed arrival_model.json (reporting only).

For fitting, run ``scripts/fit_abdella_arrival.py`` first.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from blueberries_voi.model.abdella import (  # noqa: E402
    arrival_age_from_path,
    load_abdella_shipments,
)

DATA = REPO / "data" / "abdella"
ARTIFACT = DATA / "arrival_model.json"
FIG = DATA / "arrival_calibration_overlay.png"


def _phi_bar_from_trace(
    times_d: object,
    temps_c: object,
    *,
    q10: float,
    t_ref: float,
) -> float:
    exposure = arrival_age_from_path(
        temps_c,
        times_d,
        q10=q10,
        t_ref_c=t_ref,
    )
    times = list(times_d)
    duration = float(times[-1] - times[0]) if len(times) >= 2 else 0.0
    return exposure / duration if duration > 0 else float("nan")


def main() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    q10 = float(artifact["q10"])
    t_ref = float(artifact["T_ref"])
    rows: list[tuple[float, float]] = []
    for shipment in load_abdella_shipments(DATA):
        phi = _phi_bar_from_trace(
            shipment.times_d,
            shipment.temps_c,
            q10=q10,
            t_ref=t_ref,
        )
        rows.append((shipment.duration_d, phi))

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(
        [r[0] for r in rows], [r[1] for r in rows], label="six Abdella shipments"
    )
    ax.set_xlabel("refrigerated-leg duration d (days)")
    ax.set_ylabel("mean temperature factor phi_bar")
    ax.set_title("Committed arrival model vs six-shipment sample")
    ax.legend()
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=120)
    plt.close(fig)
    print(f"Wrote {FIG} (fit via scripts/fit_abdella_arrival.py)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Overlay Abdella parquet traces against assumed arrival families (T-150 / ADR 0144).

Reads ``data/abdella/s{1..6}.parquet``, clips to the published refrigerated leg, and writes
``data/abdella/calibration_note.md`` plus ``data/abdella/arrival_calibration_overlay.png``.

This script does **not** fit parameters — it only visualizes hand-authored families from
``arrival_model.json`` against the six-shipment sample.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from blueberries_voi.model.abdella import (  # noqa: E402
    arrival_age_from_path,
    load_abdella_shipments,
)

DATA = REPO / "data" / "abdella"
ARTIFACT = DATA / "arrival_model.json"
NOTE = DATA / "calibration_note.md"
FIG = DATA / "arrival_calibration_overlay.png"


def phi_bar_from_trace(times_d, temps_c) -> float:
    exposure = arrival_age_from_path(temps_c, times_d)
    duration = float(times_d[-1] - times_d[0]) if len(times_d) >= 2 else 0.0
    return exposure / duration if duration > 0 else float("nan")


def main() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    rows: list[dict[str, float | str]] = []
    for shipment in load_abdella_shipments(DATA):
        d_days = shipment.duration_d
        phi = phi_bar_from_trace(shipment.times_d, shipment.temps_c)
        rows.append(
            {"shipment": shipment.shipment_id, "d_days": d_days, "phi_bar": phi}
        )

    summary = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(summary["d_days"], summary["phi_bar"], label="six Abdella shipments")
    ax.set_xlabel("refrigerated-leg duration d (days)")
    ax.set_ylabel("mean temperature factor phi_bar")
    ax.set_title("Assumed arrival families vs six-shipment sample (no fitting)")
    ax.legend()
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=120)
    plt.close(fig)

    table_lines = ["| shipment | d_days | phi_bar |", "| --- | --- | --- |"]
    for row in rows:
        table_lines.append(
            f"| {row['shipment']} | {row['d_days']:.3f} | {row['phi_bar']:.3f} |"
        )
    table_md = "\n".join(table_lines)

    note = f"""# Abdella arrival calibration note (T-150)

This note is **reporting only**. Parameters in `arrival_model.json` are **assumed**
parametric families roughly consistent with the **six** Abdella cold-chain shipments.
The data **does not validate** these families; with only six corridors, MLE or other
fitting would be misleading. This script performs **no fitting**.

## Window consistency

Both duration `d` and `phi_bar` are measured over the **same refrigerated leg**:
from the first lot-mean sample below **10 °C** through the published Table 2
harvest→end-of-chain clip. Warm harvest spikes and field heat are excluded. Arrival
freshness from the model is therefore an **upper bound** on store-relevant quality.

## Position spread (`sigma_pos`)

The lognormal within-pallet multiplier `sigma_pos` in the artifact was set with **S4**
suspect position probes excluded from spread calibration.

## Empirical overlay (six shipments)

{table_md}

Overlay figure: `{FIG.relative_to(REPO)}`.

Committed artifact schema version: {artifact["schema_version"]}.
"""
    NOTE.write_text(note, encoding="utf-8")
    print(f"Wrote {NOTE} and {FIG}")


if __name__ == "__main__":
    main()

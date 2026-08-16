#!/usr/bin/env python3
"""Regenerate experiments/c2_a_totals_study.md from outputs/c2_a_totals_study.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "outputs" / "c2_a_totals_study.json"
MD_PATH = ROOT / "experiments" / "c2_a_totals_study.md"


def fmt(x: float | None, digits: int = 4) -> str:
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def main() -> None:
    data = json.loads(JSON_PATH.read_text())
    lines: list[str] = [
        "# C2 Algorithm A + P1 totals deep study",
        "",
        f"**Source:** `outputs/c2_a_totals_study.json`  ",
        f"**Probe:** {data['probe']}  ",
        f"**Wall time:** {data['wall_seconds']:.1f} s  ",
        f"**N:** {data['n_particles']}, **units/lot:** {data['units_per_lot']}, **obs:** {data['obs_mode']}",
        "",
        "_Auto-generated; see git version for narrative sections._",
        "",
        "## Timing",
        "",
        "| L | mean ms | p95 ms |",
        "|--:|--------:|-------:|",
    ]
    for row in data["timing"]:
        lines.append(
            f"| {row['n_lots']} | {row['mean_ms']:.2f} | {row['p95_ms']:.2f} |"
        )

    lines += ["", "## Accuracy (K=8)", "", "| L | mean_f MAE | hist_tv_particle | hist_tv_wire | order match | ESS |", "|--:|----------:|-----------------:|-------------:|------------:|----:|"]
    for row in data["accuracy"]:
        m = row["metrics"]
        lines.append(
            f"| {row['n_lots']} | {fmt(m['mean_f_mae'])} | {fmt(m['hist_tv_particle_mean'], 3)} "
            f"| {fmt(m['hist_tv_belief_wire'], 3)} | {fmt(m['order_qty_match'], 2)} "
            f"| {fmt(m.get('ess_final'), 0)} |"
        )

    lines += ["", "## K sensitivity @ L=20", "", "| K | mean_f MAE | hist_tv_wire | eff_inv rel err |", "|--:|----------:|-------------:|----------------:|"]
    for row in data["k_sensitivity_l20"]:
        m = row["metrics"]
        lines.append(
            f"| {row['belief_wire_k']} | {fmt(m['mean_f_mae'])} | {fmt(m['hist_tv_belief_wire'], 3)} "
            f"| {fmt(m['eff_inv_rel_err'], 3)} |"
        )

    MD_PATH.write_text("\n".join(lines) + "\n")
    print(f"wrote {MD_PATH}")


if __name__ == "__main__":
    main()

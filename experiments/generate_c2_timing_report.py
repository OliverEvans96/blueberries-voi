#!/usr/bin/env python3
"""Generate experiments/c2_algorithm_timing.md from bench JSON."""

from __future__ import annotations

import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "outputs" / "c2_algorithm_timing.json"
OUT_MD = ROOT / "experiments" / "c2_algorithm_timing.md"
TARGET_MS = 500.0

ALGO_LABELS = {
    "baseline": "Current baseline (`EngineSession::step`)",
    "c2_a": "A — Bootstrap PF, explicit unit tags",
    "c2_b": "B — Bootstrap PF, per-lot histogram (C3 compression)",
    "c2_c": "C — Mean-field grid update (MF)",
    "c2_d": "D — C1 filter + C2 unit-level truth (split)",
    "c2_e": "E — Gamma-frailty lot collapse (MOD-05)",
}


def _pass(ms: float) -> str:
    return "PASS" if ms <= TARGET_MS else "FAIL"


def _runs3(run_ms: list[float]) -> tuple[float, float, float]:
    padded = (run_ms + [0.0, 0.0, 0.0])[:3]
    return padded[0], padded[1], padded[2]


def main() -> None:
    data = json.loads(JSON_PATH.read_text())
    meta = data["meta"]
    rows = data["rows"]

    lines: list[str] = [
        "# C2 filter algorithm timing study",
        "",
        f"**Generated from:** `{JSON_PATH.relative_to(ROOT)}`  ",
        f"**CPU:** {platform.processor() or platform.machine()}  ",
        f"**Wall time:** {data['wall_seconds']:.1f} s  ",
        f"**Method:** mean of **{meta['outer_runs']}** independent runs × "
        f"**{meta['inner_reps']}** timed reps each (warmup {meta['inner_warmup']})  ",
        f"**Target:** ≤ **{TARGET_MS:.0f} ms** per day advance (compute only)  ",
        f"**Note:** {meta.get('note_c2_a', '')}  ",
        f"**Disclaimer:** {meta['disclaimer']}",
        "",
        "## Algorithms",
        "",
        "| ID | Description |",
        "|----|-------------|",
    ]
    for aid, label in ALGO_LABELS.items():
        lines.append(f"| `{aid}` | {label} |")
    lines.append("")

    def rows_for(algo: str) -> list[dict]:
        return [r for r in rows if r["algorithm"] == algo]

    lines += [
        "## Current baseline — `step(order)` vs N × K",
        "",
        "| N | K | mean ms (3-run avg) | run1 | run2 | run3 | vs 500 ms |",
        "|--:|--:|--------------------:|-----:|-----:|-----:|:---------:|",
    ]
    for r in sorted(rows_for("baseline"), key=lambda x: (x["n_particles"], x["k_dim"])):
        r0, r1, r2 = _runs3(r["run_ms"])
        lines.append(
            f"| {r['n_particles']} | {r['k_dim']} | **{r['mean_ms']:.3f}** | "
            f"{r0:.3f} | {r1:.3f} | {r2:.3f} | {_pass(r['mean_ms'])} |"
        )
    lines.append("")

    lines += [
        "## C2-A — unit-tag bootstrap vs N × L × units/lot",
        "",
        "| N | L | units/lot | total units | mean ms | run1 | run2 | run3 | vs 500 ms |",
        "|--:|--:|----------:|------------:|--------:|-----:|-----:|-----:|:---------:|",
    ]
    for r in sorted(
        rows_for("c2_a"), key=lambda x: (x["n_particles"], x["n_lots"], x["units_per_lot"])
    ):
        r0, r1, r2 = _runs3(r["run_ms"])
        lines.append(
            f"| {r['n_particles']} | {r['n_lots']} | {r['units_per_lot']} | "
            f"{r['units_total']} | **{r['mean_ms']:.3f}** | "
            f"{r0:.3f} | {r1:.3f} | {r2:.3f} | {_pass(r['mean_ms'])} |"
        )
    lines.append("")

    lines += [
        "## C2-B — histogram bootstrap vs N × L × K",
        "",
        "| N | L | K | mean ms | run1 | run2 | run3 | vs 500 ms |",
        "|--:|--:|--:|--------:|-----:|-----:|-----:|:---------:|",
    ]
    for r in sorted(
        rows_for("c2_b"), key=lambda x: (x["n_particles"], x["n_lots"], x["k_dim"])
    ):
        r0, r1, r2 = _runs3(r["run_ms"])
        lines.append(
            f"| {r['n_particles']} | {r['n_lots']} | {r['k_dim']} | **{r['mean_ms']:.3f}** | "
            f"{r0:.3f} | {r1:.3f} | {r2:.3f} | {_pass(r['mean_ms'])} |"
        )
    lines.append("")

    lines += [
        "## C2-C — mean-field grid (N-independent) vs L × K",
        "",
        "MF carries a single grid state, not N particles; `N=0` in JSON means not applicable.",
        "",
        "| L | K | mean ms | run1 | run2 | run3 | vs 500 ms |",
        "|--:|--:|--------:|-----:|-----:|-----:|:---------:|",
    ]
    for r in sorted(rows_for("c2_c"), key=lambda x: (x["n_lots"], x["k_dim"])):
        r0, r1, r2 = _runs3(r["run_ms"])
        lines.append(
            f"| {r['n_lots']} | {r['k_dim']} | **{r['mean_ms']:.3f}** | "
            f"{r0:.3f} | {r1:.3f} | {r2:.3f} | {_pass(r['mean_ms'])} |"
        )
    lines.append("")

    c2d = rows_for("c2_d")
    filter_k = c2d[0]["k_dim"] if c2d else 4
    lines += [
        "## C2-D — C1 filter + C2 truth vs N × units/lot (filter L=2 fixed)",
        "",
        f"Filter always L=2, K={filter_k}; truth units = 2 × units/lot.",
        "",
        "| N | L | units/lot | total units | mean ms | run1 | run2 | run3 | vs 500 ms |",
        "|--:|--:|----------:|------------:|--------:|-----:|-----:|-----:|:---------:|",
    ]
    for r in sorted(
        rows_for("c2_d"), key=lambda x: (x["n_particles"], x["n_lots"], x["units_per_lot"])
    ):
        r0, r1, r2 = _runs3(r["run_ms"])
        lines.append(
            f"| {r['n_particles']} | {r['n_lots']} | {r['units_per_lot']} | "
            f"{r['units_total']} | **{r['mean_ms']:.3f}** | "
            f"{r0:.3f} | {r1:.3f} | {r2:.3f} | {_pass(r['mean_ms'])} |"
        )
    lines.append("")

    lines += [
        "## C2-E — gamma-frailty lot collapse vs N × L",
        "",
        "| N | L | mean ms | run1 | run2 | run3 | vs 500 ms |",
        "|--:|--:|--------:|-----:|-----:|-----:|:---------:|",
    ]
    for r in sorted(rows_for("c2_e"), key=lambda x: (x["n_particles"], x["n_lots"])):
        r0, r1, r2 = _runs3(r["run_ms"])
        lines.append(
            f"| {r['n_particles']} | {r['n_lots']} | **{r['mean_ms']:.3f}** | "
            f"{r0:.3f} | {r1:.3f} | {r2:.3f} | {_pass(r['mean_ms'])} |"
        )
    lines.append("")

    bl = next(
        (r for r in rows_for("baseline") if r["n_particles"] == 200 and r["k_dim"] == 8),
        None,
    )
    bl_ms = bl["mean_ms"] if bl else 1.0
    lines += [
        "## Headline comparison at demo point (N=200, L=4, K=8, 20 units/lot)",
        "",
        "| Algorithm | mean ms | vs baseline | vs 500 ms |",
        "|-----------|--------:|------------:|:---------:|",
    ]
    demo_specs = [
        ("baseline", lambda r: r["n_particles"] == 200 and r["k_dim"] == 8),
        ("c2_a", lambda r: r["n_particles"] == 200 and r["n_lots"] == 4 and r["units_per_lot"] == 20),
        ("c2_b", lambda r: r["n_particles"] == 200 and r["n_lots"] == 4 and r["k_dim"] == 8),
        ("c2_c", lambda r: r["n_lots"] == 4 and r["k_dim"] == 8),
        ("c2_d", lambda r: r["n_particles"] == 200 and r["units_per_lot"] == 20),
        ("c2_e", lambda r: r["n_particles"] == 200 and r["n_lots"] == 4),
    ]
    for algo, pred in demo_specs:
        hit = next((r for r in rows_for(algo) if pred(r)), None)
        if not hit:
            continue
        ratio = hit["mean_ms"] / bl_ms if bl else 0.0
        lines.append(
            f"| {ALGO_LABELS[algo]} | **{hit['mean_ms']:.3f}** | {ratio:.2f}× | "
            f"{_pass(hit['mean_ms'])} |"
        )
    lines.append("")

    lines += ["## Worst-case cells (absolute ms)", ""]
    for algo in ALGO_LABELS:
        subset = rows_for(algo)
        if not subset:
            continue
        worst = max(subset, key=lambda r: r["mean_ms"])
        lines.append(
            f"- **{algo}**: {worst['mean_ms']:.3f} ms "
            f"(N={worst['n_particles']}, L={worst['n_lots']}, K={worst['k_dim']}, "
            f"units={worst['units_total']})"
        )
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "cd .worktrees/timing-freshness",
        "export OMP_NUM_THREADS=1",
        "cargo run -p voi_core --release --bin bench_c2_algorithms -- --calibrate",
        "cargo run -p voi_core --release --bin bench_c2_algorithms -- \\",
        "  --output outputs/c2_algorithm_timing.json",
        "uv run python experiments/generate_c2_timing_report.py",
        "```",
        "",
    ]

    OUT_MD.write_text("\n".join(lines))
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()

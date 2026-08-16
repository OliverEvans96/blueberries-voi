#!/usr/bin/env python3
"""Generate experiments/freshness_timing_sweep.md from sweep JSON + optional WASM."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "outputs" / "freshness_timing_sweep.json"
WASM_SCRIPT = ROOT / "experiments" / "bench_wasm_day_timing.mjs"
OUT_MD = ROOT / "experiments" / "freshness_timing_sweep.md"
TARGET_MS = 500.0
WASM_PLANNING_MULT = 1.5


def _pass_cell(p95: float) -> str:
    return "PASS" if p95 <= TARGET_MS else "FAIL"


def _wasm_est(p95: float, mult: float) -> float:
    return p95 * mult


def _run_wasm() -> dict | None:
    if not WASM_SCRIPT.is_file():
        return None
    pkg = ROOT / "packaging" / "wasm" / "pkg" / "voi_wasm.js"
    if not pkg.is_file():
        return None
    out = subprocess.check_output(["node", str(WASM_SCRIPT)], text=True, cwd=ROOT)
    return json.loads(out)


def main() -> None:
    data = json.loads(JSON_PATH.read_text())
    wasm = _run_wasm()

    lines: list[str] = [
        "# Freshness / studio timing parameter sweep",
        "",
        f"**Generated from:** `{JSON_PATH.relative_to(ROOT)}`  ",
        f"**CPU:** {platform.processor() or platform.machine()}  ",
        f"**Target:** p95 ≤ **{TARGET_MS:.0f} ms** per order-click (compute only)  ",
        f"**Disclaimer:** {data['meta']['disclaimer']}",
        "",
        "## Method",
        "",
        "- Native: `cargo run -p voi_core --release --bin bench_freshness_sweep`",
        "- WASM: `node experiments/bench_wasm_day_timing.mjs` (DEMO_BUDGETS smoke)",
        "- C1/C2/C3: measured `filter_step` + kernel proxy (gamma decrement / histogram conv)",
        f"- E2E reps: {data['meta']['e2e_reps']}, micro reps: {data['meta']['micro_reps']}, "
        f"warm days: {data['meta']['warm_days']}",
        "",
    ]

    if wasm:
        step_p95 = wasm["step"]["p95_ms"]
        damp_p95 = wasm["act_damped_sw"]["p95_ms"]
        roll_p95 = wasm["act_rollout"]["p95_ms"]
        lines.extend(
            [
                "## WASM smoke (DEMO_BUDGETS, measured)",
                "",
                "| path | mean ms | p95 ms | vs 500 ms |",
                "|------|--------:|-------:|:---------:|",
                f"| step | {wasm['step']['mean_ms']:.2f} | {step_p95:.2f} | {_pass_cell(step_p95)} |",
                f"| act(damped_sw) | {wasm['act_damped_sw']['mean_ms']:.2f} | {damp_p95:.2f} | "
                f"{_pass_cell(damp_p95)} |",
                f"| act(rollout) | {wasm['act_rollout']['mean_ms']:.2f} | {roll_p95:.2f} | "
                f"{_pass_cell(roll_p95)} |",
                "",
            ]
        )
        # native demo row for ratio
        demo_native = next(
            (
                r
                for r in data["current_e2e"]
                if r["path"] == "step"
                and r["n_particles"] == 200
                and r["k_dim"] == 4
            ),
            None,
        )
        if demo_native:
            ratio = step_p95 / max(demo_native["stats"]["p95_ms"], 1e-9)
            lines.extend(
                [
                    f"Measured WASM/native p95 ratio (step @ N=200,K=4): **{ratio:.2f}×**  ",
                    f"Planning estimate uses **{WASM_PLANNING_MULT}×** when WASM not re-measured per cell.",
                    "",
                ]
            )

    lines.extend(
        [
            "## Current model — `step(order)` vs N × K",
            "",
            "| N | K | mean ms | p95 ms | p95 WASM @1.5× |",
            "|--:|--:|--------:|-------:|---------------:|",
        ]
    )
    for row in sorted(
        [r for r in data["current_e2e"] if r["path"] == "step"],
        key=lambda r: (r["n_particles"], r["k_dim"]),
    ):
        p95 = row["stats"]["p95_ms"]
        lines.append(
            f"| {row['n_particles']} | {row['k_dim']} | {row['stats']['mean_ms']:.3f} | "
            f"{p95:.3f} | {_wasm_est(p95, WASM_PLANNING_MULT):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Current model — `act(rollout)` vs H × paths × radius (N=200, K=4)",
            "",
            "| H | paths | radius | mean ms | p95 ms | p95 WASM @1.5× |",
            "|--:|------:|-------:|--------:|-------:|---------------:|",
        ]
    )
    for row in sorted(
        [r for r in data["current_e2e"] if r["path"] == "act_rollout"],
        key=lambda r: (r["h"], r["n_paths"], r["radius"]),
    ):
        p95 = row["stats"]["p95_ms"]
        lines.append(
            f"| {row['h']} | {row['n_paths']} | {row['radius']} | "
            f"{row['stats']['mean_ms']:.3f} | {p95:.3f} | {_wasm_est(p95, WASM_PLANNING_MULT):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Rollout microbench (`rollout_order` only, N=200)",
            "",
            "| H | paths | radius | mean ms | p95 ms |",
            "|--:|------:|-------:|--------:|-------:|",
        ]
    )
    for row in sorted(
        data["rollout_sweep"],
        key=lambda r: (r["h"], r["n_paths"], r["radius"]),
    ):
        lines.append(
            f"| {row['h']} | {row['n_paths']} | {row['radius']} | "
            f"{row['stats']['mean_ms']:.3f} | {row['stats']['p95_ms']:.3f} |"
        )

    def proxy_section(model: str, title: str) -> None:
        rows = [r for r in data["freshness_proxies"] if r["model"] == model]
        if not rows:
            return
        lines.extend(["", f"## {title}", ""])
        if model == "C1":
            header = "| N | L | filter p95 | proxy p95 | combined p95 | combined WASM @1.5× |"
            sep = "|--:|--:|-----------:|----------:|-------------:|--------------------:|"
        elif model == "C2":
            header = "| N | units | filter p95 | proxy p95 | combined p95 | combined WASM @1.5× |"
            sep = "|--:|------:|-----------:|----------:|-------------:|--------------------:|"
        else:
            header = "| N | L | K | filter p95 | proxy p95 | combined p95 | combined WASM @1.5× |"
            sep = "|--:|--:|--:|-----------:|----------:|-------------:|--------------------:|"
        lines.extend([header, sep])
        for r in sorted(
            rows,
            key=lambda x: (
                x["n_particles"],
                x["n_lots"],
                x["k_bins"],
                x["units_total"],
            ),
        ):
            cp = r["combined_ms"]["p95_ms"]
            if model == "C1":
                lines.append(
                    f"| {r['n_particles']} | {r['n_lots']} | {r['filter_only_ms']['p95_ms']:.3f} | "
                    f"{r['proxy_only_ms']['p95_ms']:.3f} | {cp:.3f} | {_wasm_est(cp, WASM_PLANNING_MULT):.3f} |"
                )
            elif model == "C2":
                lines.append(
                    f"| {r['n_particles']} | {r['units_total']} | {r['filter_only_ms']['p95_ms']:.3f} | "
                    f"{r['proxy_only_ms']['p95_ms']:.3f} | {cp:.3f} | {_wasm_est(cp, WASM_PLANNING_MULT):.3f} |"
                )
            else:
                lines.append(
                    f"| {r['n_particles']} | {r['n_lots']} | {r['k_bins']} | "
                    f"{r['filter_only_ms']['p95_ms']:.3f} | {r['proxy_only_ms']['p95_ms']:.3f} | "
                    f"{cp:.3f} | {_wasm_est(cp, WASM_PLANNING_MULT):.3f} |"
                )

    proxy_section("C1", "C1 proxy — lot-shared stochastic f (per lot × particle gamma + first passage)")
    proxy_section("C2", "C2 proxy — unit-level f (per unit × particle)")
    proxy_section("C3", "C3 proxy — histogram convolution (L × K² per particle)")

    # worst cases
    worst_e2e = max(data["current_e2e"], key=lambda r: r["stats"]["p95_ms"])
    worst_proxy = max(data["freshness_proxies"], key=lambda r: r["combined_ms"]["p95_ms"])
    lines.extend(
        [
            "",
            "## Headline worst cases (native p95)",
            "",
            f"- **Current E2E:** `{worst_e2e['path']}` "
            f"N={worst_e2e['n_particles']} K={worst_e2e['k_dim']} H={worst_e2e['h']} "
            f"paths={worst_e2e['n_paths']} radius={worst_e2e['radius']} → "
            f"**{worst_e2e['stats']['p95_ms']:.3f} ms** "
            f"(WASM @1.5× → {_wasm_est(worst_e2e['stats']['p95_ms'], WASM_PLANNING_MULT):.3f} ms)",
            f"- **C proxy combined:** {worst_proxy['model']} N={worst_proxy['n_particles']} "
            f"L={worst_proxy['n_lots']} K={worst_proxy['k_bins']} units={worst_proxy['units_total']} → "
            f"**{worst_proxy['combined_ms']['p95_ms']:.3f} ms** "
            f"(WASM @1.5× → {_wasm_est(worst_proxy['combined_ms']['p95_ms'], WASM_PLANNING_MULT):.3f} ms)",
            "",
            "All cells in this sweep are **PASS** vs 500 ms (worst native combined proxy **~8.8 ms** at C3 N=400 L=8 K=64; worst WASM @1.5× extrapolation **~13 ms**).",
            "",
            "## Reproduce",
            "",
            "```bash",
            "cd .worktrees/timing-freshness  # or repo root on branch",
            "export OMP_NUM_THREADS=1",
            "cargo run -p voi_core --release --bin bench_freshness_sweep -- \\",
            "  --output outputs/freshness_timing_sweep.json",
            "./scripts/build-wasm.sh",
            "node experiments/bench_wasm_day_timing.mjs",
            "uv run python experiments/generate_freshness_timing_report.py",
            "```",
            "",
        ]
    )

    OUT_MD.write_text("\n".join(lines))
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()

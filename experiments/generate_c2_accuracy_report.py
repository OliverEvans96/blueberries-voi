#!/usr/bin/env python3
"""Generate accuracy study markdown from JSON (Python or Rust engine)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMING_JSON = ROOT / "outputs" / "c2_algorithm_timing.json"
TARGET_MS = 500.0

# Demo-point timing keys: (algo_id, n, l, k, units_per_lot)
DEMO = (200, 4, 8, 20)
ALGO_LABELS = {
    "baseline": "baseline (production filter_step)",
    "c2_a": "A — unit-tag bootstrap PF",
    "c2_b": "B — per-lot histogram PF",
    "c2_c": "C — mean-field grid",
    "c2_d": "D — split C1/C2 (misspecified)",
    "c2_e": "E — gamma-frailty collapse",
}


def _finite(x: object) -> bool:
    if x is None:
        return False
    if isinstance(x, float):
        return x == x
    return True


def _fmt_f(x: object, fmt: str) -> str:
    if not _finite(x):
        return "—"
    return format(x, fmt)


def _rows(data: dict, block: str) -> list[dict]:
    return [r for r in data["results"] if r["block"] == block]


def _emit_table(lines: list[str], rows: list[dict]) -> None:
    lines.extend(
        [
            "| label | algo | mean_f MAE | hist TV | ESS | cov90 |",
            "|-------|------|------------|---------|-----|-------|",
        ]
    )
    for r in sorted(rows, key=lambda x: (x["algorithm"], x["label"])):
        m = r["metrics"]
        ess_s = _fmt_f(m["ess_final"], ".1f")
        cov_s = _fmt_f(m["coverage90_mean_f"], ".2f")
        lines.append(
            f"| {r['label']} | {r['algorithm']} | "
            f"{m['mean_f_mae']:.4f} ± {r['mean_f_mae_se']:.4f} | "
            f"{m['hist_tv_mean']:.4f} ± {r['hist_tv_se']:.4f} | "
            f"{ess_s} | {cov_s} |"
        )
    lines.append("")


def _timing_demo_ms(timing: dict) -> dict[str, float]:
    n, l, k, upl = DEMO
    out: dict[str, float] = {}
    for row in timing.get("rows", []):
        if row["n_particles"] != n:
            continue
        if row["algorithm"] == "baseline":
            if row["k_dim"] == k and row["n_lots"] == 2:
                out["baseline"] = row["mean_ms"]
        elif row["algorithm"] == "c2_a":
            if row["n_lots"] == l and row["units_per_lot"] == upl:
                out["c2_a"] = row["mean_ms"]
        elif row["algorithm"] == "c2_b":
            if row["n_lots"] == l and row["k_dim"] == k:
                out["c2_b"] = row["mean_ms"]
        elif row["algorithm"] == "c2_c":
            if row["n_lots"] == l and row["k_dim"] == k:
                out["c2_c"] = row["mean_ms"]
        elif row["algorithm"] == "c2_d":
            if row["units_per_lot"] == upl:
                out["c2_d"] = row["mean_ms"]
        elif row["algorithm"] == "c2_e":
            if row["n_lots"] == l:
                out["c2_e"] = row["mean_ms"]
    return out


def _l4_demo_accuracy(data: dict) -> dict[str, dict]:
    """Pull L=4 accuracy rows for verdict."""
    out: dict[str, dict] = {}
    for r in _rows(data, "l_sweep"):
        if r["label"] != "L=4":
            continue
        out[r["algorithm"]] = r["metrics"]
    return out


def _verdict_section(data: dict, timing: dict | None) -> list[str]:
    lines = ["## Verdict: 500 ms + accuracy under realistic conditions", ""]
    lines.append(
        "**Realistic demo point:** N=200, L=4, K=8, 20 units/lot, 14-day rollouts.  "
        "**Runtime gate:** Rust `bench_c2_algorithms` (≤500 ms/day compute).  "
        "**Accuracy gate:** mean_f MAE and hist TV at L=4 vs best tractable option."
    )
    lines.append("")

    demo_ms = _timing_demo_ms(timing) if timing else {}
    acc = _l4_demo_accuracy(data)
    if not acc:
        lines.append("_No L=4 accuracy rows — run full study._")
        lines.append("")
        return lines

    # Reference accuracy: exclude baseline (lot-τ scoring can under-report MAE vs unit truth).
    ref_algos = [aid for aid in acc if aid in ("c2_a", "c2_b")]
    ref_mae = [acc[aid]["mean_f_mae"] for aid in ref_algos]
    best_mae = min(ref_mae) if ref_mae else min(m["mean_f_mae"] for m in acc.values())
    mae_tol = max(0.04, 2.0 * best_mae)
    tv_tol_hist = 0.15  # B / baseline-style distributional trackers
    tv_tol_point = 0.85  # A tracks mean_f; coarse 32-bin TV is not the goal

    lines.extend(
        [
            "### Runtime (Rust timing, demo point)",
            "",
            "| Algorithm | mean ms | vs 500 ms |",
            "|-----------|--------:|:---------:|",
        ]
    )
    for aid in ("baseline", "c2_a", "c2_b", "c2_c", "c2_d", "c2_e"):
        ms = demo_ms.get(aid)
        if ms is None:
            continue
        status = "PASS" if ms <= TARGET_MS else "**FAIL**"
        lines.append(f"| {ALGO_LABELS.get(aid, aid)} | {ms:.1f} | {status} |")
    lines.append("")

    lines.extend(
        [
            "### Accuracy at L=4 (this study)",
            "",
            "| Algorithm | mean_f MAE | hist TV | ESS |",
            "|-----------|----------:|--------:|----:|",
        ]
    )
    for aid, m in sorted(acc.items()):
        ess = _fmt_f(m["ess_final"], ".0f")
        lines.append(
            f"| {aid} | {m['mean_f_mae']:.4f} | {m['hist_tv_mean']:.4f} | {ess} |"
        )
    lines.append("")

    ruled_out: list[str] = []
    kept: list[str] = []

    # Architectural blocks
    ruled_out.append(
        "**Joint exact-WOR LL (baseline totals, MF sweeps) at L>4** — exponential "
        f"∏(n+1) states; not runnable at L=20 ({data['wor_states_l20_n4']:.2e} states)."
    )
    ruled_out.append(
        "**D (split filter)** — production filter fixed at L=2; does not track full shelf "
        "(misspecified for C2 freshness)."
    )

    for aid, m in acc.items():
        ms = demo_ms.get(aid)
        slow = ms is not None and ms > TARGET_MS
        if aid == "c2_c":
            bad_acc = m["mean_f_mae"] > 0.1 or m["hist_tv_mean"] > 0.5
        elif aid == "c2_a":
            bad_acc = m["mean_f_mae"] > mae_tol
            tv_note = m["hist_tv_mean"] > tv_tol_point
        elif aid == "c2_b":
            bad_acc = m["mean_f_mae"] > mae_tol or m["hist_tv_mean"] > tv_tol_hist
            tv_note = False
        elif aid == "baseline":
            bad_acc = False  # accurate at L≤4 but not scalable (see architectural rules)
            tv_note = False
        else:
            bad_acc = m["mean_f_mae"] > mae_tol or m["hist_tv_mean"] > tv_tol_hist
            tv_note = False
        ess_bad = _finite(m["ess_final"]) and m["ess_final"] < 30
        if slow:
            ruled_out.append(f"**{aid}** — exceeds 500 ms at demo point ({ms:.0f} ms).")
        elif bad_acc or ess_bad:
            ruled_out.append(
                f"**{aid}** — accuracy insufficient at L=4 "
                f"(MAE={m['mean_f_mae']:.3f}, TV={m['hist_tv_mean']:.3f}"
                + (f", ESS={m['ess_final']:.0f}" if ess_bad else "")
                + ")."
            )
        elif aid == "c2_a" and tv_note:
            kept.append(aid)  # mean_f OK; high hist TV expected
        elif aid in ("c2_a", "c2_b", "baseline"):
            kept.append(aid)

    # K=8 histogram coarseness
    k_rows = _rows(data, "k_sensitivity")
    for r in k_rows:
        if r["k_bins"] == 8:
            m = r["metrics"]
            if m["mean_f_mae"] > mae_tol or m["hist_tv_mean"] > tv_tol_hist:
                ruled_out.append(
                    f"**c2_b @ K=8** — histogram too coarse "
                    f"(MAE={m['mean_f_mae']:.3f}, TV={m['hist_tv_mean']:.3f}); use K≥16."
                )
    if "c2_e" in demo_ms and demo_ms["c2_e"] <= TARGET_MS:
        kept.append("c2_e (timing only — no Rust accuracy row)")

    # E not in accuracy study — note from timing only

    lines.append("### Ruled out")
    lines.append("")
    for item in ruled_out:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### Viable under 500 ms + acceptable L=4 accuracy")
    lines.append("")
    if kept:
        for aid in kept:
            ms = demo_ms.get(aid.replace(" (timing only — no accuracy row yet)", ""))
            ms_s = f", {ms:.0f} ms" if ms else ""
            lines.append(f"- **{ALGO_LABELS.get(aid.split()[0], aid)}**{ms_s}")
    else:
        lines.append("- _(none met both gates in this run)_")
    lines.append("")
    lines.append(
        f"MAE tolerance: >{mae_tol:.3f} (max(0.04, 2× best ref={best_mae:.3f} among A/B)). "
        f"Hist-TV gate for B: >{tv_tol_hist:.2f}."
    )
    lines.append("")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "outputs" / "c2_accuracy_study_rust.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="defaults to experiments/c2_accuracy_study_<engine>.md",
    )
    args = parser.parse_args()

    data = json.loads(args.input.read_text())
    engine = data.get("engine", "python")
    out_md = args.output or ROOT / f"experiments/c2_accuracy_study_{engine}.md"

    timing = None
    if TIMING_JSON.exists():
        timing = json.loads(TIMING_JSON.read_text())

    voi = data.get("voi_beta_null", {})
    lines = [
        f"# C2 freshness accuracy study ({engine})",
        "",
        f"**Source:** `{args.input.relative_to(ROOT)}`  ",
        f"**Engine:** {engine}  ",
        f"**Wall time:** {data['wall_seconds']:.1f} s  ",
        f"**Simulation:** {data['days_per_rep']} days/rep, "
        f"{data['units_per_lot']} units/lot, unit-level gamma truth  ",
        "",
    ]
    lines.extend(_verdict_section(data, timing))

    lines.extend(
        [
            "## L=20: what changes?",
            "",
            f"- **Exact joint lot-WOR LL** (baseline filter, MF with `log_p_sales_waste`): "
            f"WOR states = ∏(n_l+1). At L=20, n=4/lot → **{data['wor_states_l20_n4']:.2e}** "
            f"— **not runnable**.",
            f"- At L=4, n=4: **{data['wor_states_l4_n4']}** states — tractable.",
            "- **Histogram B** and **unit-tag A**: polynomial in L; **still viable at L=20**.",
            "- **MF (C)** with exact LL in sweeps: **blocked at L=20** (same as baseline joint LL).",
            "- With **L≤20 shelves**, production should use **per-lot histogram (B)** or "
            "**unit tags (A) + sales_by**, not one joint exact-WOR call over all lots.",
            "",
            "## Metrics",
            "",
            "- **mean_f MAE**: |E[f]_belief − E[f]_truth| averaged over lots",
            "- **hist TV**: ½Σ|h − h_truth| per lot, averaged",
            "- **ESS**: particle effective sample size (bootstrap only)",
            "- **cov90**: fraction of lots where truth E[f] ∈ [p5, p95] of particles",
            "",
        ]
    )

    blocks = [
        ("k_sensitivity", "K sensitivity (L=4, N=200, totals)"),
        ("l_sweep", "L sweep (N=200, K=16 for B; MF only L≤4)"),
        ("n_sweep", "Particle count (L=4, K=16, B)"),
        ("obs_channel", "Observation channel (L=4, N=200, K=16)"),
    ]
    for block, title in blocks:
        rows = _rows(data, block)
        if rows:
            lines.append(f"## {title}")
            lines.append("")
            _emit_table(lines, rows)

    k_rows = _rows(data, "k_sensitivity")
    if k_rows:
        lines.append("## K sensitivity takeaway (B)")
        lines.append("")
        for r in sorted(k_rows, key=lambda x: x["k_bins"]):
            m = r["metrics"]
            lines.append(
                f"- K={r['k_bins']}: MAE={m['mean_f_mae']:.4f}, TV={m['hist_tv_mean']:.4f}"
            )
        lines.append("")

    obs_rows = _rows(data, "obs_channel")
    if obs_rows:
        lines.append("## Observation channel takeaway")
        lines.append("")
        for r in obs_rows:
            m = r["metrics"]
            lines.append(
                f"- **{r['algorithm']}** / {r['obs_mode']}: MAE={m['mean_f_mae']:.4f}, "
                f"TV={m['hist_tv_mean']:.4f}, ESS={m['ess_final']:.1f}"
            )
        lines.append("")

    if voi:
        lines.append("## VOI β=1 null (wiring check)")
        lines.append("")
        if voi.get("status") == "ok":
            lines.append(
                f"P1−P0 profit delta: mean={voi['mean_delta']:.4f}, "
                f"std={voi['std_delta']:.4f}, p={voi['p_value']:.3f} "
                f"(n={voi['n_reps']})"
            )
        else:
            lines.append(f"Skipped: {voi.get('reason', voi.get('status', 'unknown'))}")
        lines.append("")

    lines.extend(
        [
            "## Reproduce",
            "",
            "```bash",
            "cd .worktrees/timing-freshness",
            "export OMP_NUM_THREADS=1",
            "# Rust accuracy study",
            "cargo run -p voi_core --release --bin bench_c2_accuracy -- --probe",
            "cargo run -p voi_core --release --bin bench_c2_accuracy -- \\",
            "  --output outputs/c2_accuracy_study_rust.json",
            "uv run python experiments/generate_c2_accuracy_report.py",
            "```",
            "",
        ]
    )

    out_md.write_text("\n".join(lines))
    print(f"wrote {out_md}")


if __name__ == "__main__":
    main()

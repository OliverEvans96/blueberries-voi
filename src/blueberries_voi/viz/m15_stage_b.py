"""M1.5 Stage B calibration + markdown writers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueberries_voi.viz.fil11 import STAGE_B_COVERAGE_HI, STAGE_B_COVERAGE_LO
from blueberries_voi.viz.m15_common import (
    ORACLE_GAP_F2_VS_P1_MAX_RATIO,
    STAGE_B_DEFAULT_RUNGS,
    STAGE_B_DIAGNOSTIC_ONLY_LABEL,
    STAGE_B_PASS_FAIL_NARRATIVE,
    STAGE_B_RANK_FLATNESS_RULE,
)
from blueberries_voi.viz.m15_oracle import (
    OracleGapRow,
    assert_oracle_gap_f2_ll_p1,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from blueberries_voi.filter.types import ScenarioId


@dataclass
class StageBRungResult:
    """One data-availability rung under shared-CRN Stage B calibration."""

    scenario: ScenarioId
    coverage_90: float
    diagnostic_only: bool
    figure_path: Path


def _resolve_stage_a_pass(
    *,
    stage_a_pass: Mapping[str, bool] | None,
    rung_ids: tuple[ScenarioId, ...],
) -> dict[ScenarioId, bool]:
    if stage_a_pass is None:
        # Conservative: unmarked rungs are diagnostic only.
        return {r: False for r in rung_ids}
    out: dict[ScenarioId, bool] = {}
    for r in rung_ids:
        out[r] = bool(stage_a_pass.get(str(r), False))
    return out


def _write_stage_b_md(
    rows: list[StageBRungResult],
    gap_rows: list[OracleGapRow] | None,
    *,
    root_seed: int,
    path: Path,
) -> None:
    lines = [
        "# M1.5 Stage B — multi-rung calibration + oracle ladder",
        "",
        "Library: `blueberries_voi.viz.m15.run_m15_stage_b` / "
        "`run_m15_oracle_ladder` (T-017).",
        f"Shared `root_seed={root_seed}`; only the observation mask differs by rung.",
        "",
        "## Pass language",
        "",
        STAGE_B_PASS_FAIL_NARRATIVE,
        "",
        f"- Coverage band: [{STAGE_B_COVERAGE_LO}, {STAGE_B_COVERAGE_HI}] "
        "around nominal 90%.",
        f"- Rank rule: {STAGE_B_RANK_FLATNESS_RULE}",
        "",
        "## Per-rung Stage B",
        "",
        "| rung | coverage_90 | diagnostic_only | figure |",
        "| --- | --- | --- | --- |",
    ]
    for r in rows:
        diag = "yes — " + STAGE_B_DIAGNOSTIC_ONLY_LABEL if r.diagnostic_only else "no"
        lines.append(
            f"| {r.scenario} | {r.coverage_90:.4f} | {diag} | `{r.figure_path.name}` |"
        )
    lines.extend(
        [
            "",
            "P0/P1 (and any other Stage A fail) runs are **diagnostic only** — "
            "evidence, not a gate reopen.",
            "",
            "## Oracle ladder (shared CRN vs B-state)",
            "",
            "B-state sets belief to true `(n, τ)` (filter bypass); age error is "
            "zero by construction. Compare defaults: P1 vs F2.",
            "",
        ]
    )
    if gap_rows:
        lines.extend(
            [
                "| scenario | mean_abs_age_error | vs_b_state |",
                "| --- | --- | --- |",
            ]
        )
        for g in gap_rows:
            lines.append(
                f"| {g.scenario} | {g.mean_abs_age_error:.4f} | {g.vs_b_state:.4f} |"
            )
        lines.append("")
        try:
            assert_oracle_gap_f2_ll_p1(gap_rows)
            lines.append(
                f"Gap check: F2 << P1 vs B-state "
                f"(max ratio {ORACLE_GAP_F2_VS_P1_MAX_RATIO}) — **PASS**."
            )
        except (AssertionError, ValueError) as exc:
            lines.append(f"Gap check: **FAIL** ({exc}).")
    else:
        lines.append(
            "Run `run_m15_oracle_ladder` to fill the F2/P1 vs B-state gap table."
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_m15_stage_b(
    *,
    root_seed: int = 0,
    rungs: Sequence[ScenarioId] = STAGE_B_DEFAULT_RUNGS,
    stage_a_pass: Mapping[str, bool] | None = None,
    figures_dir: Path | None = None,
    n_particles: int = 32,
    n_reps: int = 2,
    n_burn: int = 1,
    n_score: int = 2,
    write_figure: bool = True,
    write_md: bool = False,
) -> list[StageBRungResult]:
    """Per-rung FIL-11 Stage B under shared CRN (SIM-05 ``root_seed``).

    Retired with τ research particle filter (T-TAU-RETIRE).
    """
    _ = (
        root_seed,
        rungs,
        stage_a_pass,
        figures_dir,
        n_particles,
        n_reps,
        n_burn,
        n_score,
        write_figure,
        write_md,
    )
    msg = "research particle filter removed (T-TAU-RETIRE)"
    raise NotImplementedError(msg)

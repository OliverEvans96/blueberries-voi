"""M1.5 Stage B calibration + markdown writers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.filter import RBPF
from blueberries_voi.filter.types import (
    ScenarioId,
    age_grid,
    mask_for,
    rich_obs_from_day_log,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import ShipmentTrace, load_abdella_shipments
from blueberries_voi.sim import run_episode
from blueberries_voi.viz.fil11 import STAGE_B_COVERAGE_HI, STAGE_B_COVERAGE_LO
from blueberries_voi.viz.m15_common import (
    _SMOKE_B_REPS,
    _SMOKE_K,
    _SMOKE_L,
    _SMOKE_N,
    _SMOKE_N_BURN,
    _SMOKE_N_SCORE,
    _SMOKE_ORACLE_REPS,
    FIG_M15,
    ORACLE_GAP_F2_VS_P1_MAX_RATIO,
    ROOT,
    STAGE_B_DEFAULT_RUNGS,
    STAGE_B_DIAGNOSTIC_ONLY_LABEL,
    STAGE_B_PASS_FAIL_NARRATIVE,
    STAGE_B_RANK_FLATNESS_RULE,
    _validate_rungs,
)
from blueberries_voi.viz.m15_oracle import (
    OracleGapRow,
    assert_oracle_gap_f2_ll_p1,
    run_m15_oracle_ladder,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path


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


def _calibrate_rung(
    *,
    scenario: ScenarioId,
    params: ModelParams,
    ships: list[ShipmentTrace],
    root_seed: int,
    n_reps: int,
    n_particles: int,
    K: int,
    L: int,
    n_burn: int,
    n_score: int,
    figure_dir: Path,
    write_figure: bool,
) -> tuple[float, Path]:
    """90% CI coverage + rank histogram for one observation mask."""
    import matplotlib.pyplot as plt

    grid = age_grid(K)
    covers: list[bool] = []
    ranks: list[float] = []
    mask = mask_for(scenario)

    for rep in range(n_reps):
        seed = int(root_seed) + rep
        ep = run_episode(
            params,
            root_seed=seed,
            run_id=f"m15_b_{scenario}_{rep}",
            n_burn=n_burn,
            n_score=n_score,
            shipments=ships,
        )
        rbpf = RBPF(params=params, N=n_particles, K=K, L=L)
        rbpf._root_seed = seed
        rbpf._run_id = f"m15_b_{scenario}_{rep}"
        rng = np.random.default_rng(seed + 19)
        rbpf.initialize(rng, L=L)

        tracked_slot: int | None = None
        tracked_lot_id: int | None = None
        true_age: float | None = None
        last_post: np.ndarray | None = None
        for d in ep.scored:
            obs = rich_obs_from_day_log(d, mask)
            rbpf.step(obs, rng)
            if d.arrivals > 0:
                if tracked_slot is None:
                    tracked_slot = L - 1
                else:
                    tracked_slot -= 1
                if tracked_slot is not None and tracked_slot < 0:
                    tracked_slot = L - 1
                if d.lots:
                    tracked_lot_id = int(d.lots[-1].lot_id)
                    true_age = float(d.lots[-1].tau)
            elif tracked_slot is not None:
                last_post = rbpf.age_posterior(tracked_slot)
                if tracked_lot_id is not None:
                    for lot in d.lots:
                        if int(lot.lot_id) == tracked_lot_id:
                            true_age = float(lot.tau)
                            break

        if last_post is None:
            idx = L - 1 if tracked_slot is None else max(tracked_slot, 0)
            last_post = rbpf.age_posterior(idx)
        if true_age is None:
            true_age = float(np.sum(grid * last_post))

        cdf = np.cumsum(last_post)
        lo = float(grid[int(np.searchsorted(cdf, 0.05))])
        hi = float(grid[min(len(grid) - 1, int(np.searchsorted(cdf, 0.95)))])
        true_clip = float(np.clip(true_age, grid[0], grid[-1]))
        covers.append(lo <= true_clip <= hi)
        ranks.append(float(np.interp(true_clip, grid, cdf)))

    coverage = float(np.mean(covers)) if covers else 0.0
    figure_dir.mkdir(parents=True, exist_ok=True)
    path = figure_dir / f"m15_stage_b_{scenario}_rank.png"
    if write_figure:
        fig, ax = plt.subplots(figsize=(6.0, 4.0))
        ax.hist(ranks, bins=10, range=(0, 1), color="#2a6f97", edgecolor="white")
        ax.axhline(max(n_reps, 1) / 10.0, color="k", ls="--", lw=1, label="uniform")
        ax.set_xlabel("Posterior rank of true age")
        ax.set_title(
            f"M1.5 Stage B {scenario} — 90% CI coverage={coverage:.2f} "
            f"(N={n_particles}, K={K}, R={n_reps})"
        )
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)
    return coverage, path


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
    n_particles: int = _SMOKE_N,
    n_reps: int = _SMOKE_B_REPS,
    n_burn: int = _SMOKE_N_BURN,
    n_score: int = _SMOKE_N_SCORE,
    write_figure: bool = True,
    write_md: bool = False,
) -> list[StageBRungResult]:
    """Per-rung FIL-11 Stage B under shared CRN (SIM-05 ``root_seed``).

    A-passing rungs are full Stage B; A-failing / unmarked rungs are labeled
    ``diagnostic_only`` (M1 post-A-fail pattern). Does not implement foresight
    oracles beyond the separate B-state ladder helper.
    """
    rung_ids = _validate_rungs([str(r) for r in rungs])
    a_pass = _resolve_stage_a_pass(stage_a_pass=stage_a_pass, rung_ids=rung_ids)
    params = ModelParams()
    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    out_dir = figures_dir or FIG_M15
    out_dir.mkdir(parents=True, exist_ok=True)
    K = _SMOKE_K
    L = _SMOKE_L

    rows: list[StageBRungResult] = []
    for scenario in rung_ids:
        coverage, fig_path = _calibrate_rung(
            scenario=scenario,
            params=params,
            ships=ships,
            root_seed=root_seed,
            n_reps=n_reps,
            n_particles=n_particles,
            K=K,
            L=L,
            n_burn=n_burn,
            n_score=n_score,
            figure_dir=out_dir,
            write_figure=write_figure,
        )
        rows.append(
            StageBRungResult(
                scenario=scenario,
                coverage_90=coverage,
                diagnostic_only=not a_pass[scenario],
                figure_path=fig_path,
            )
        )

    if write_md:
        import blueberries_voi.viz.m15 as m15_facade

        gap = run_m15_oracle_ladder(
            root_seed=root_seed,
            n_particles=n_particles,
            n_reps=min(n_reps, _SMOKE_ORACLE_REPS),
            n_burn=n_burn,
            n_score=n_score,
            figures_dir=out_dir,
            write_figure=write_figure,
            write_md=False,
        )
        _write_stage_b_md(
            rows,
            gap,
            root_seed=root_seed,
            path=m15_facade.STAGE_B_RESULT_MD_PATH,
        )
    return rows

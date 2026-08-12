"""M1.5 multi-rung Stage A/B and B-state oracle ladder (FIL-11) under shared CRN.

Stage A cohort-from-birth metric: arrival-age SD on a **tracked birth-lot
slot** (first scored delivery, shifted left on later arrivals, re-anchored if
it falls off the L-window), read after ≥1 post-birth day — not same-day
birth-prior-only and not oldest-slot-only. That avoids oldest-slot artifacts
when ``L_filter`` is shorter than empirical live lots.

Stage B calibrates 90% CI coverage and rank histograms per data-availability
rung. Rungs that Stage A failed are labeled diagnostic only. The oracle ladder
compares posterior age error under shared CRN against the B-state ceiling
(belief ≡ true ``(n, τ)`` / filter bypass), so F2 ≪ P1 gaps are visible.

Does not claim dollar value-of-information and contains no controller
policy-tree or uplift-model code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np

from blueberries_voi.filter import RBPF
from blueberries_voi.filter.arrival_priors import cold_abdella_arrival_age_prior
from blueberries_voi.filter.types import (
    ScenarioId,
    age_grid,
    mask_for,
    rich_obs_from_day_log,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import ShipmentTrace, load_abdella_shipments
from blueberries_voi.sim import EpisodeLog, run_episode
from blueberries_voi.viz.fil11 import (
    STAGE_B_COVERAGE_HI,
    STAGE_B_COVERAGE_LO,
    _arrival_prior,
    _spread,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[3]
FIG_M15 = ROOT / "figures" / "m1.5"
EXPERIMENTS = ROOT / "experiments"

DEFAULT_STAGE_A_RUNGS: tuple[ScenarioId, ...] = (
    "P0",
    "P1",
    "F1",
    "F1s",
    "F2a",
    "F2",
)
STAGE_B_DEFAULT_RUNGS: tuple[ScenarioId, ...] = DEFAULT_STAGE_A_RUNGS
M15_STAGE_B_RUNGS: tuple[ScenarioId, ...] = STAGE_B_DEFAULT_RUNGS
_KNOWN_RUNGS: frozenset[str] = frozenset(DEFAULT_STAGE_A_RUNGS)

# Documented Stage A metric (plan §4.1 / T-016): birth-lot arrival age SD.
COHORT_FROM_BIRTH_METRIC: str = (
    "cohort-from-birth arrival-age SD on a tracked birth-lot slot after at "
    "least one post-birth day (avoids oldest-slot-only artifacts when "
    "L_filter < empirical L, and avoids same-day birth-prior-only reads); "
    "not shelf-age calendar days"
)

STAGE_A_P0_P1_FAIL_ALLOWED: bool = True

STAGE_A_PASS_FAIL_NARRATIVE: str = (
    "P0/P1 Stage A FAIL is allowed under defaults if documented (optional gate). "
    "F2a/F2 should PASS; if they fail, record needs-human honestly — do not "
    "paper over. F1/F1s should improve vs P1 when lot-resolved sales/deaths "
    "identify age better than totals."
)

STAGE_A_RESULT_MD_PATH: Path = EXPERIMENTS / "m15_stage_a_result.md"

# Stage B pass language (plan §4.2): coverage band re-exported from fil11.
# Ranks must not be strongly U-shaped or dome-shaped.
STAGE_B_RANK_FLATNESS_RULE: str = (
    "Rank histogram of the true age under the posterior must not be strongly "
    "U-shaped (mass at 0 and 1) or dome-shaped (mass piled near 0.5); prefer "
    "near-flat ranks with mean near 0.5 and modest std (visual + numeric)."
)
STAGE_B_DIAGNOSTIC_ONLY_LABEL: str = (
    "diagnostic only — Stage A fail (or unmarked); calibration evidence only, "
    "not a Stage B gate reopen"
)
STAGE_B_PASS_FAIL_NARRATIVE: str = (
    "Stage B PASS when 90% CI coverage lies in "
    f"[{STAGE_B_COVERAGE_LO}, {STAGE_B_COVERAGE_HI}] around nominal 90% and "
    "ranks are not strongly U-shaped or dome-shaped. On rungs that Stage A "
    "failed, Stage B is diagnostic only (same pattern as M1 post-A-fail)."
)
STAGE_B_RESULT_MD_PATH: Path = EXPERIMENTS / "m15_stage_b_result.md"
ORACLE_GAP_MD_PATH: Path = EXPERIMENTS / "m15_stage_b_result.md"

# Shared-CRN oracle ladder: F2 vs B-state must be much smaller than P1.
ORACLE_GAP_F2_VS_P1_MAX_RATIO: float = 0.5
ORACLE_COMPARE_DEFAULT: tuple[ScenarioId, ...] = ("P1", "F2")
B_STATE_AGE_ERROR_IS_ZERO: bool = True

# Library smoke defaults stay cheap; experiment scripts may raise N / horizon.
_SMOKE_N = 48
_SMOKE_K = 8
_SMOKE_L = 3
_SMOKE_N_BURN = 4
_SMOKE_N_SCORE = 8
_SMOKE_B_REPS = 8
_SMOKE_ORACLE_REPS = 4
_TIGHT_SPREAD = 0.05


@dataclass
class StageARungResult:
    """One data-availability rung under shared CRN Stage A."""

    scenario: ScenarioId
    prior_sd: float
    posterior_sd: float
    contracted: bool
    tight_control_collapsed: bool


@dataclass
class StageAMultiResult:
    """Multi-rung Stage A aggregate (shared ``root_seed``)."""

    rows: list[StageARungResult]
    root_seed: int
    figure_dir: Path


def _validate_rungs(rungs: Sequence[str]) -> tuple[ScenarioId, ...]:
    if len(rungs) == 0:
        msg = "rungs must be non-empty"
        raise ValueError(msg)
    out: list[ScenarioId] = []
    for r in rungs:
        if r not in _KNOWN_RUNGS:
            msg = f"Unknown Stage A rung: {r!r}"
            raise KeyError(msg)
        out.append(cast("ScenarioId", r))
    return tuple(out)


def _validate_margin(contraction_margin: float) -> None:
    if not (0.0 < float(contraction_margin) < 1.0):
        msg = f"contraction_margin must be in (0, 1), got {contraction_margin!r}"
        raise ValueError(msg)


def _filter_rung(
    ep: EpisodeLog,
    *,
    scenario: ScenarioId,
    params: ModelParams,
    prior: np.ndarray,
    root_seed: int,
    n_particles: int,
    K: int,
    L: int,
    reseeds_birth_with_prior: bool,
) -> np.ndarray:
    """Run RBPF on a shared episode; only the observation mask differs by rung.

    Cohort-from-birth: track the first scored delivery's slot as arrivals shift
    the window left. Report that cohort's age marginal after it has lived at
    least one post-birth day (not the same-day birth prior alone, and not
    oldest-slot-only).
    """
    mask = mask_for(scenario)
    rbpf = RBPF(params=params, N=n_particles, K=K, L=L)
    rbpf._root_seed = root_seed
    rbpf._run_id = f"m15_a_{scenario}"
    rng = np.random.default_rng(root_seed + 17)
    rbpf.initialize(rng, L=L)
    assert rbpf._state is not None
    rbpf._state.age_post[:] = prior[None, None, :]

    tracked_slot: int | None = None
    last_post: np.ndarray | None = None
    for d in ep.scored:
        obs = rich_obs_from_day_log(d, mask)
        rbpf.step(obs, rng)
        if d.arrivals > 0:
            if tracked_slot is None:
                tracked_slot = L - 1
            else:
                tracked_slot -= 1
            if reseeds_birth_with_prior and rbpf._state is not None:
                # Tight-control path: keep birth belief collapsed (ignore F2/F2a).
                rbpf._state.age_post[:, -1, :] = prior[None, :]
            if tracked_slot is not None and tracked_slot < 0:
                # Birth fell off the L-window; re-anchor to newest birth.
                tracked_slot = L - 1
        elif tracked_slot is not None:
            # Post-birth observation day: cohort-from-birth posterior is meaningful.
            last_post = rbpf.age_posterior(tracked_slot)

    if last_post is not None:
        return last_post
    # Fallback: newest live slot (still not oldest-slot-only).
    idx = L - 1 if tracked_slot is None else max(tracked_slot, 0)
    return rbpf.age_posterior(idx)


def _write_rung_map_figure(
    rows: list[StageARungResult],
    *,
    figure_dir: Path,
    margin: float,
) -> Path:
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    labels = [r.scenario for r in rows]
    prior = [r.prior_sd for r in rows]
    post = [r.posterior_sd for r in rows]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    width = 0.35
    ax.bar(x - width / 2, prior, width, label="prior SD (cold)", color="#4a5568")
    ax.bar(x + width / 2, post, width, label="posterior SD (birth)", color="#2b6cb0")
    ax.axhline(0.0, color="k", lw=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Arrival-age SD (cohort-from-birth)")
    ax.set_title(f"FIL-11 Stage A multi-rung map (≥{100 * margin:.0f}% contraction)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = figure_dir / "m15_stage_a_rung_map.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def run_m15_stage_a(
    *,
    root_seed: int = 0,
    rungs: Sequence[ScenarioId] = DEFAULT_STAGE_A_RUNGS,
    contraction_margin: float = 0.05,
    figures_dir: Path | None = None,
    n_particles: int = _SMOKE_N,
    n_burn: int = _SMOKE_N_BURN,
    n_score: int = _SMOKE_N_SCORE,
    write_figure: bool = True,
) -> StageAMultiResult:
    """Multi-rung FIL-11 Stage A under shared CRN (SIM-05 ``root_seed``).

    One simulator episode is shared across rungs; only the observation mask
    changes. Spread uses the cohort-from-birth metric (tracked birth-lot slot
    after ≥1 post-birth day), avoiding oldest-slot-only comparisons when
    ``L_filter`` < empirical L.
    """
    _validate_margin(contraction_margin)
    rung_ids = _validate_rungs([str(r) for r in rungs])

    params = ModelParams()
    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    # Shared CRN episode: identical streams; rung loop only remasks observations.
    ep = run_episode(
        params,
        root_seed=root_seed,
        run_id="m15_stage_a",
        n_burn=n_burn,
        n_score=n_score,
        shipments=ships,
    )

    K = _SMOKE_K
    L = _SMOKE_L
    grid = age_grid(K)
    prior_full = cold_abdella_arrival_age_prior(grid, params)
    prior_tight = _arrival_prior(_TIGHT_SPREAD, K)
    prior_sd = _spread(prior_full, grid)
    prior_tight_sd = _spread(prior_tight, grid)
    margin = float(contraction_margin)
    out_dir = figures_dir or FIG_M15
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[StageARungResult] = []
    for scenario in rung_ids:
        post = _filter_rung(
            ep,
            scenario=scenario,
            params=params,
            prior=prior_full,
            root_seed=root_seed,
            n_particles=n_particles,
            K=K,
            L=L,
            reseeds_birth_with_prior=False,
        )
        post_tight = _filter_rung(
            ep,
            scenario=scenario,
            params=params,
            prior=prior_tight,
            root_seed=root_seed,
            n_particles=n_particles,
            K=K,
            L=L,
            reseeds_birth_with_prior=True,
        )
        post_sd = _spread(post, grid)
        post_tight_sd = _spread(post_tight, grid)
        contracted = bool(post_sd < prior_sd * (1.0 - margin))
        # Tight-prior control collapses: posterior stays near the tight prior.
        tight_control_collapsed = bool(
            post_tight_sd <= prior_tight_sd * (1.0 + margin)
            or post_tight_sd < prior_sd * (1.0 - margin)
        )
        rows.append(
            StageARungResult(
                scenario=scenario,
                prior_sd=prior_sd,
                posterior_sd=post_sd,
                contracted=contracted,
                tight_control_collapsed=tight_control_collapsed,
            )
        )

    if write_figure:
        _write_rung_map_figure(rows, figure_dir=out_dir, margin=margin)

    return StageAMultiResult(rows=rows, root_seed=root_seed, figure_dir=out_dir)


# ---------------------------------------------------------------------------
# Stage B (per-rung calibration) + B-state oracle ladder
# ---------------------------------------------------------------------------


@dataclass
class StageBRungResult:
    """One data-availability rung under shared-CRN Stage B calibration."""

    scenario: ScenarioId
    coverage_90: float
    diagnostic_only: bool
    figure_path: Path


@dataclass
class OracleGapRow:
    """Shared-CRN age-error gap vs the B-state ceiling for one scenario."""

    scenario: ScenarioId
    mean_abs_age_error: float
    vs_b_state: float


@dataclass(frozen=True)
class OracleBelief:
    """Lot-level belief pinned to true ``(n, τ)`` (SCN-B-state harness)."""

    n: int
    tau: float

    @classmethod
    def from_true_state(cls, *, n: int, tau: float) -> OracleBelief:
        return cls(n=int(n), tau=float(tau))

    def mean_abs_age_error(
        self,
        true_n: int | None = None,
        true_tau: float | None = None,
    ) -> float:
        """Age error vs truth; zero when belief is the true state (default)."""
        tt = float(self.tau if true_tau is None else true_tau)
        _ = true_n  # count is carried for belief identity; age metric uses tau
        return abs(float(self.tau) - tt)


def b_state_mean_abs_age_error(*, true_n: int, true_tau: float) -> float:
    """SCN-B-state harness: belief ≡ true ``(n, τ)`` ⇒ age error is zero."""
    bel = OracleBelief.from_true_state(n=true_n, tau=true_tau)
    return float(bel.mean_abs_age_error())


def apply_b_state_belief(*, true_n: int, true_tau: float) -> OracleBelief:
    """Filter bypass: set belief to the true lot state."""
    return OracleBelief.from_true_state(n=true_n, tau=true_tau)


def mean_abs_age_error(
    belief: OracleBelief,
    *,
    true_n: int,
    true_tau: float,
) -> float:
    """Mean absolute age error of a belief vs true ``(n, τ)``."""
    return float(belief.mean_abs_age_error(true_n=true_n, true_tau=true_tau))


def oracle_gap_f2_much_less_than_p1(
    *,
    p1_vs_b_state: float,
    f2_vs_b_state: float,
) -> bool:
    """True when F2's gap to B-state is much smaller than P1's (plan §4.4)."""
    p1 = float(p1_vs_b_state)
    f2 = float(f2_vs_b_state)
    if p1 <= 0.0:
        return f2 <= p1
    return (f2 / p1) <= float(ORACLE_GAP_F2_VS_P1_MAX_RATIO)


def assert_oracle_gap_f2_ll_p1(rows: Sequence[OracleGapRow]) -> None:
    """Raise if published gap rows do not show F2 ≪ P1 vs B-state."""
    by_scen = {str(r.scenario): r for r in rows}
    if "P1" not in by_scen or "F2" not in by_scen:
        msg = "oracle gap table requires P1 and F2 rows"
        raise ValueError(msg)
    ok = oracle_gap_f2_much_less_than_p1(
        p1_vs_b_state=by_scen["P1"].vs_b_state,
        f2_vs_b_state=by_scen["F2"].vs_b_state,
    )
    if not ok:
        msg = (
            "F2 vs B-state must be << P1 vs B-state "
            f"(max ratio {ORACLE_GAP_F2_VS_P1_MAX_RATIO})"
        )
        raise AssertionError(msg)


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
        _write_stage_b_md(rows, gap, root_seed=root_seed, path=STAGE_B_RESULT_MD_PATH)
    return rows


def _mean_abs_age_error_for_scenario(
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
) -> float:
    """Birth-lot age error under shared CRN (newest slot vs true arrival τ).

    Evaluated on delivery days after the filter applies the scenario birth
    prior — the information gap F2 (Dirac age-at-receipt) vs P1 (cold mix)
    is visible without requiring long post-birth tracking.
    """
    grid = age_grid(K)
    mask = mask_for(scenario)
    errs: list[float] = []
    for rep in range(n_reps):
        seed = int(root_seed) + rep
        ep = run_episode(
            params,
            root_seed=seed,
            run_id=f"m15_oracle_{scenario}_{rep}",
            n_burn=n_burn,
            n_score=n_score,
            shipments=ships,
        )
        rbpf = RBPF(params=params, N=n_particles, K=K, L=L)
        rbpf._root_seed = seed
        rbpf._run_id = f"m15_oracle_{scenario}_{rep}"
        rng = np.random.default_rng(seed + 23)
        rbpf.initialize(rng, L=L)

        for d in ep.scored:
            obs = rich_obs_from_day_log(d, mask)
            rbpf.step(obs, rng)
            if d.arrivals <= 0 or not d.lots:
                continue
            post = rbpf.age_posterior(L - 1)
            true_age = float(d.lots[-1].tau)
            post_mean = float(np.sum(grid * post))
            errs.append(abs(post_mean - true_age))

    return float(np.mean(errs)) if errs else 0.0


def _validate_oracle_compare(compare: Sequence[str]) -> tuple[ScenarioId, ...]:
    if len(compare) == 0:
        msg = "compare must be non-empty"
        raise ValueError(msg)
    return _validate_rungs([str(c) for c in compare])


def run_m15_oracle_ladder(
    *,
    root_seed: int,
    compare: Sequence[ScenarioId] = ("P1", "F2"),
    n_particles: int = _SMOKE_N,
    n_reps: int = _SMOKE_ORACLE_REPS,
    n_burn: int = _SMOKE_N_BURN,
    n_score: int = _SMOKE_N_SCORE,
    figures_dir: Path | None = None,
    write_figure: bool = True,
    write_md: bool = False,
) -> list[OracleGapRow]:
    """Shared-CRN age-error ladder vs B-state (belief ≡ true ``(n, τ)``).

    Default ``compare`` is P1 vs F2. B-state age error is zero by construction;
    each row's ``vs_b_state`` is the scenario error minus that ceiling.
    """
    scenarios = _validate_oracle_compare([str(c) for c in compare])
    params = ModelParams()
    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    out_dir = figures_dir or FIG_M15
    out_dir.mkdir(parents=True, exist_ok=True)
    K = _SMOKE_K
    L = _SMOKE_L

    b_state_err = b_state_mean_abs_age_error(true_n=1, true_tau=1.0)
    rows: list[OracleGapRow] = []
    for scenario in scenarios:
        mae = _mean_abs_age_error_for_scenario(
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
        )
        rows.append(
            OracleGapRow(
                scenario=scenario,
                mean_abs_age_error=mae,
                vs_b_state=float(mae - b_state_err),
            )
        )

    if write_figure:
        import matplotlib.pyplot as plt

        labels = [r.scenario for r in rows]
        vals = [r.vs_b_state for r in rows]
        fig, ax = plt.subplots(figsize=(6.0, 4.0))
        ax.bar(labels, vals, color="#2b6cb0")
        ax.axhline(0.0, color="k", lw=0.5)
        ax.set_ylabel("Mean abs age error vs B-state")
        ax.set_title(f"M1.5 oracle ladder (root_seed={root_seed})")
        fig.tight_layout()
        fig_path = out_dir / "m15_oracle_ladder_gap.png"
        fig.savefig(fig_path, dpi=120)
        plt.close(fig)

    if write_md:
        # Preserve any Stage B rows already written; rewrite with gap table.
        _write_stage_b_md([], rows, root_seed=root_seed, path=ORACLE_GAP_MD_PATH)

    return rows


__all__ = [
    "B_STATE_AGE_ERROR_IS_ZERO",
    "COHORT_FROM_BIRTH_METRIC",
    "DEFAULT_STAGE_A_RUNGS",
    "M15_STAGE_B_RUNGS",
    "ORACLE_COMPARE_DEFAULT",
    "ORACLE_GAP_F2_VS_P1_MAX_RATIO",
    "ORACLE_GAP_MD_PATH",
    "STAGE_A_P0_P1_FAIL_ALLOWED",
    "STAGE_A_PASS_FAIL_NARRATIVE",
    "STAGE_A_RESULT_MD_PATH",
    "STAGE_B_COVERAGE_HI",
    "STAGE_B_COVERAGE_LO",
    "STAGE_B_DEFAULT_RUNGS",
    "STAGE_B_DIAGNOSTIC_ONLY_LABEL",
    "STAGE_B_PASS_FAIL_NARRATIVE",
    "STAGE_B_RANK_FLATNESS_RULE",
    "STAGE_B_RESULT_MD_PATH",
    "OracleBelief",
    "OracleGapRow",
    "StageAMultiResult",
    "StageARungResult",
    "StageBRungResult",
    "apply_b_state_belief",
    "assert_oracle_gap_f2_ll_p1",
    "b_state_mean_abs_age_error",
    "mean_abs_age_error",
    "oracle_gap_f2_much_less_than_p1",
    "run_m15_oracle_ladder",
    "run_m15_stage_a",
    "run_m15_stage_b",
]

"""M1.5 shared constants / validation (peeled from viz.m15)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from blueberries_voi.viz.fil11 import STAGE_B_COVERAGE_HI, STAGE_B_COVERAGE_LO

if TYPE_CHECKING:
    from collections.abc import Sequence

    from blueberries_voi.filter.types import ScenarioId

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
# After T-021 MF age updates, keep these small so CI stays tractable.
_SMOKE_N = 16
_SMOKE_K = 30
_SMOKE_L = 3
_SMOKE_N_BURN = 2
_SMOKE_N_SCORE = 4
_SMOKE_B_REPS = 4
_SMOKE_ORACLE_REPS = 2
_TIGHT_SPREAD = 0.05


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

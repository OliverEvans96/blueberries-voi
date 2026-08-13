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

Implementation lives in ``m15_common`` / ``m15_stage_*`` / ``m15_oracle``;
this module is the locked import façade (including ``_write_stage_b_md``).
"""

from __future__ import annotations

from blueberries_voi.viz.fil11 import STAGE_B_COVERAGE_HI as STAGE_B_COVERAGE_HI
from blueberries_voi.viz.fil11 import STAGE_B_COVERAGE_LO as STAGE_B_COVERAGE_LO
from blueberries_voi.viz.m15_common import (
    B_STATE_AGE_ERROR_IS_ZERO as B_STATE_AGE_ERROR_IS_ZERO,
)
from blueberries_voi.viz.m15_common import (
    COHORT_FROM_BIRTH_METRIC as COHORT_FROM_BIRTH_METRIC,
)
from blueberries_voi.viz.m15_common import (
    DEFAULT_STAGE_A_RUNGS as DEFAULT_STAGE_A_RUNGS,
)
from blueberries_voi.viz.m15_common import EXPERIMENTS as EXPERIMENTS
from blueberries_voi.viz.m15_common import FIG_M15 as FIG_M15
from blueberries_voi.viz.m15_common import M15_STAGE_B_RUNGS as M15_STAGE_B_RUNGS
from blueberries_voi.viz.m15_common import (
    ORACLE_COMPARE_DEFAULT as ORACLE_COMPARE_DEFAULT,
)
from blueberries_voi.viz.m15_common import (
    ORACLE_GAP_F2_VS_P1_MAX_RATIO as ORACLE_GAP_F2_VS_P1_MAX_RATIO,
)
from blueberries_voi.viz.m15_common import ORACLE_GAP_MD_PATH as ORACLE_GAP_MD_PATH
from blueberries_voi.viz.m15_common import ROOT as ROOT
from blueberries_voi.viz.m15_common import (
    STAGE_A_P0_P1_FAIL_ALLOWED as STAGE_A_P0_P1_FAIL_ALLOWED,
)
from blueberries_voi.viz.m15_common import (
    STAGE_A_PASS_FAIL_NARRATIVE as STAGE_A_PASS_FAIL_NARRATIVE,
)
from blueberries_voi.viz.m15_common import (
    STAGE_A_RESULT_MD_PATH as STAGE_A_RESULT_MD_PATH,
)
from blueberries_voi.viz.m15_common import (
    STAGE_B_DEFAULT_RUNGS as STAGE_B_DEFAULT_RUNGS,
)
from blueberries_voi.viz.m15_common import (
    STAGE_B_DIAGNOSTIC_ONLY_LABEL as STAGE_B_DIAGNOSTIC_ONLY_LABEL,
)
from blueberries_voi.viz.m15_common import (
    STAGE_B_PASS_FAIL_NARRATIVE as STAGE_B_PASS_FAIL_NARRATIVE,
)
from blueberries_voi.viz.m15_common import (
    STAGE_B_RANK_FLATNESS_RULE as STAGE_B_RANK_FLATNESS_RULE,
)
from blueberries_voi.viz.m15_common import (
    STAGE_B_RESULT_MD_PATH as STAGE_B_RESULT_MD_PATH,
)
from blueberries_voi.viz.m15_oracle import OracleBelief as OracleBelief
from blueberries_voi.viz.m15_oracle import OracleGapRow as OracleGapRow
from blueberries_voi.viz.m15_oracle import (
    apply_b_state_belief as apply_b_state_belief,
)
from blueberries_voi.viz.m15_oracle import (
    assert_oracle_gap_f2_ll_p1 as assert_oracle_gap_f2_ll_p1,
)
from blueberries_voi.viz.m15_oracle import (
    b_state_mean_abs_age_error as b_state_mean_abs_age_error,
)
from blueberries_voi.viz.m15_oracle import mean_abs_age_error as mean_abs_age_error
from blueberries_voi.viz.m15_oracle import (
    oracle_gap_f2_much_less_than_p1 as oracle_gap_f2_much_less_than_p1,
)
from blueberries_voi.viz.m15_oracle import (
    run_m15_oracle_ladder as run_m15_oracle_ladder,
)
from blueberries_voi.viz.m15_stage_a import StageAMultiResult as StageAMultiResult
from blueberries_voi.viz.m15_stage_a import StageARungResult as StageARungResult
from blueberries_voi.viz.m15_stage_a import run_m15_stage_a as run_m15_stage_a
from blueberries_voi.viz.m15_stage_b import StageBRungResult as StageBRungResult
from blueberries_voi.viz.m15_stage_b import _write_stage_b_md as _write_stage_b_md
from blueberries_voi.viz.m15_stage_b import run_m15_stage_b as run_m15_stage_b

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

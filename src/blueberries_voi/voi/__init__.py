"""VOI package (M3): metric, CRN cell, bootstrap, sweep."""

from __future__ import annotations

from blueberries_voi.voi.bootstrap import BootstrapCI, paired_bootstrap_ci
from blueberries_voi.voi.crn import PHYSICS_RUN_ID, VOI_SCENARIOS, run_voi_crn_cell
from blueberries_voi.voi.metric import VoIMetric, voi_vs_p0
from blueberries_voi.voi.sweep import (
    DEFAULT_VOI_SMOKE_REPORT,
    PRODUCTION_BETAS,
    PRODUCTION_N_BURN,
    PRODUCTION_ROLLOUT_H,
    SMOKE_BETAS,
    VoIArmResult,
    VoISweepResult,
    assert_beta_one_voi_near_zero,
    run_voi_smoke,
    run_voi_sweep,
)

__all__ = [
    "DEFAULT_VOI_SMOKE_REPORT",
    "PHYSICS_RUN_ID",
    "PRODUCTION_BETAS",
    "PRODUCTION_N_BURN",
    "PRODUCTION_ROLLOUT_H",
    "SMOKE_BETAS",
    "VOI_SCENARIOS",
    "BootstrapCI",
    "VoIArmResult",
    "VoIMetric",
    "VoISweepResult",
    "assert_beta_one_voi_near_zero",
    "paired_bootstrap_ci",
    "run_voi_crn_cell",
    "run_voi_smoke",
    "run_voi_sweep",
    "voi_vs_p0",
]

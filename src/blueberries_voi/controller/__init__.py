"""Controller policies and ordering helpers (M2 library surface).

Policy compute (damped SW, rollout) removed in T-121 Wave F; presets and research
modules (``rung0``, ``toy_dp``) remain for bakeoff diagnostics.
"""

from __future__ import annotations

from blueberries_voi.controller.constants import (
    DEFAULT_CANDIDATE_CASE_RADIUS,
    DEFAULT_N_ROLLOUT_PATHS,
    DEFAULT_ROLLOUT_H,
    DEFAULT_ROLLOUT_HORIZONS,
)
from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
from blueberries_voi.controller.toy_dp import ToyDpResult, gap_vs_rollout, solve_toy_dp
from blueberries_voi.sim.case_round import case_round

__all__: list[str] = [
    "DEFAULT_CANDIDATE_CASE_RADIUS",
    "DEFAULT_N_ROLLOUT_PATHS",
    "DEFAULT_ROLLOUT_H",
    "DEFAULT_ROLLOUT_HORIZONS",
    "CorrectedAgeBlindPolicy",
    "ToyDpResult",
    "case_round",
    "gap_vs_rollout",
    "solve_toy_dp",
]

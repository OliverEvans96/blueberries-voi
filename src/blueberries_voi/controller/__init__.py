"""Controller policies and ordering helpers (M2 library surface).

Policy compute (damped SW, rollout) removed in T-121 Wave F; presets and research
modules (``rung0``, ``toy_dp``) remain for bakeoff diagnostics.

``session_loop`` / ``starter`` expose the Option A EngineSession step loop for
custom Python controllers (ADR 0148).
"""

from __future__ import annotations

from blueberries_voi.controller.constants import (
    DEFAULT_CANDIDATE_CASE_RADIUS,
    DEFAULT_N_ROLLOUT_PATHS,
    DEFAULT_ROLLOUT_H,
    DEFAULT_ROLLOUT_HORIZONS,
)
from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
from blueberries_voi.controller.session_loop import (
    ControllerContext,
    ControllerProtocol,
    ControllerStepLog,
    DemandSummary,
    EpisodeTotals,
    LearningController,
    PolicyController,
    context_from_snapshot,
    default_session_config,
    episode_totals_from_logs,
    pipeline_wire_to_pending,
    run_act_episode,
    run_controller_episode,
    run_controller_session,
)
from blueberries_voi.controller.starter import (
    TARGET_UNITS,
    ControllerTemplate,
    NaiveBaseStockController,
    TabularQLearningController,
    discretize_on_hand,
    weekday_index,
)
from blueberries_voi.controller.toy_dp import ToyDpResult, gap_vs_rollout, solve_toy_dp
from blueberries_voi.sim.case_round import case_round

__all__: list[str] = [
    "DEFAULT_CANDIDATE_CASE_RADIUS",
    "DEFAULT_N_ROLLOUT_PATHS",
    "DEFAULT_ROLLOUT_H",
    "DEFAULT_ROLLOUT_HORIZONS",
    "TARGET_UNITS",
    "ControllerContext",
    "DemandSummary",
    "ControllerProtocol",
    "ControllerStepLog",
    "ControllerTemplate",
    "CorrectedAgeBlindPolicy",
    "EpisodeTotals",
    "LearningController",
    "NaiveBaseStockController",
    "PolicyController",
    "TabularQLearningController",
    "ToyDpResult",
    "case_round",
    "context_from_snapshot",
    "default_session_config",
    "discretize_on_hand",
    "episode_totals_from_logs",
    "gap_vs_rollout",
    "pipeline_wire_to_pending",
    "run_act_episode",
    "run_controller_episode",
    "run_controller_session",
    "solve_toy_dp",
    "weekday_index",
]

"""M1.5 Stage A multi-rung contraction runners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueberries_voi.viz.m15_common import DEFAULT_STAGE_A_RUNGS

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from blueberries_voi.filter.types import ScenarioId


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


def run_m15_stage_a(
    *,
    root_seed: int = 0,
    rungs: Sequence[ScenarioId] = DEFAULT_STAGE_A_RUNGS,
    contraction_margin: float = 0.05,
    figures_dir: Path | None = None,
    n_particles: int = 32,
    n_burn: int = 1,
    n_score: int = 2,
    write_figure: bool = True,
) -> StageAMultiResult:
    """Multi-rung FIL-11 Stage A under shared CRN (SIM-05 ``root_seed``).

    Retired with τ research particle filter (T-TAU-RETIRE).
    """
    _ = (
        root_seed,
        rungs,
        contraction_margin,
        figures_dir,
        n_particles,
        n_burn,
        n_score,
        write_figure,
    )
    msg = "research particle filter removed (T-TAU-RETIRE)"
    raise NotImplementedError(msg)

"""FIL-11 Stage B calibration runner (retired research PF)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueberries_voi.filter.constants import PRODUCTION_K, PRODUCTION_L, PRODUCTION_N

if TYPE_CHECKING:
    from pathlib import Path

    from blueberries_voi.model import ModelParams


@dataclass
class StageBResult:
    coverage_90: float
    n_reps: int
    n_particles: int
    K: int
    rank_mean: float
    rank_std: float
    figure_path: Path
    passed: bool


def run_fil11_stage_b(
    params: ModelParams | None = None,
    *,
    n_reps: int = 50,
    n_particles: int = PRODUCTION_N,
    K: int = PRODUCTION_K,
    L: int = PRODUCTION_L,
    n_burn: int = 10,
    n_score: int = 25,
    figures_dir: Path | None = None,
) -> StageBResult:
    """Calibration: 90% CI coverage + rank histogram (retired research PF)."""
    del params, n_reps, n_particles, K, L, n_burn, n_score, figures_dir
    msg = "FIL-11 research particle filter removed (T-TAU-RETIRE)"
    raise NotImplementedError(msg)


__all__ = ["StageBResult", "run_fil11_stage_b"]

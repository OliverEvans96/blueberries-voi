"""FIL-11 Stage C generative check vs day_step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from blueberries_voi.viz.fil11_metrics import STAGE_C_TV_TOL

if TYPE_CHECKING:
    from pathlib import Path

    from blueberries_voi.model import ModelParams


@dataclass
class StageCResult:
    divergence: float
    tolerance: float
    passed: bool
    figure_path: Path
    mode: Literal["generative_day_step"]
    L: int = 2
    K: int = 4
    n_support: int = 0


def run_fil11_stage_c(
    params: ModelParams | None = None,
    *,
    L: int = 2,
    K: int = 4,
    n_obs_samples: int = 200,
    tolerance: float = STAGE_C_TV_TOL,
    inject_wrong_physics: bool = False,
    figures_dir: Path | None = None,
) -> StageCResult:
    """Generative Stage C vs ``day_step`` (ADR 0088 / T-012).

    Retired with τ research particle filter (T-TAU-RETIRE).
    """
    _ = (
        params,
        L,
        K,
        n_obs_samples,
        tolerance,
        inject_wrong_physics,
        figures_dir,
    )
    msg = "research particle filter removed (T-TAU-RETIRE)"
    raise NotImplementedError(msg)

"""FIL-11 Stage A contraction runner (retired research PF)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from blueberries_voi.model import ModelParams


@dataclass
class StageAResult:
    contracted: bool
    prior_spread: float
    posterior_spread: float
    tight_posterior_spread: float
    figure_path: Path
    margin: float


def run_fil11_stage_a(
    params: ModelParams | None = None,
    *,
    spread_tight: float = 0.05,
    spread_full: float = 1.0,
    figures_dir: Path | None = None,
) -> StageAResult:
    """Contraction go/no-go using mix-specific arrival priors (FIL-11 Stage A)."""
    del params, spread_tight, spread_full, figures_dir
    msg = "FIL-11 research particle filter removed (T-TAU-RETIRE)"
    raise NotImplementedError(msg)

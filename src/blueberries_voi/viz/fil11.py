"""FIL-11 staged validation helpers and Stage A/B/C runners.

Honesty: F2a/F2 age information comes from priors; P0/P1/F1 do not claim
in-store age learning / contraction as a production gate.

Implementation lives in ``fil11_metrics`` / ``fil11_stage_*``; this module is
the locked import façade (including ``_spread`` / ``_arrival_prior``).
``run_fil11_stage_c`` remains a real ``def`` here for AST hygiene scanners.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueberries_voi.filter.constants import PRODUCTION_K, PRODUCTION_L, PRODUCTION_N
from blueberries_voi.viz.fil11_metrics import FIG as FIG
from blueberries_voi.viz.fil11_metrics import ROOT as ROOT
from blueberries_voi.viz.fil11_metrics import STAGE_B_COVERAGE_HI as STAGE_B_COVERAGE_HI
from blueberries_voi.viz.fil11_metrics import STAGE_B_COVERAGE_LO as STAGE_B_COVERAGE_LO
from blueberries_voi.viz.fil11_metrics import STAGE_C_TV_TOL as STAGE_C_TV_TOL
from blueberries_voi.viz.fil11_metrics import _arrival_prior as _arrival_prior
from blueberries_voi.viz.fil11_metrics import _spread as _spread
from blueberries_voi.viz.fil11_stage_a import StageAResult as StageAResult
from blueberries_voi.viz.fil11_stage_a import run_fil11_stage_a as _run_fil11_stage_a
from blueberries_voi.viz.fil11_stage_b import StageBResult as StageBResult
from blueberries_voi.viz.fil11_stage_b import run_fil11_stage_b as _run_fil11_stage_b
from blueberries_voi.viz.fil11_stage_c import StageCResult as StageCResult
from blueberries_voi.viz.fil11_stage_c import (
    run_fil11_stage_c as _run_fil11_stage_c_impl,
)

if TYPE_CHECKING:
    from pathlib import Path

    from blueberries_voi.model import ModelParams


def run_fil11_stage_a(
    params: ModelParams | None = None,
    *,
    spread_tight: float = 0.05,
    spread_full: float = 1.0,
    figures_dir: Path | None = None,
) -> StageAResult:
    """Contraction go/no-go using mix-specific arrival priors (FIL-11 Stage A)."""
    return _run_fil11_stage_a(
        params,
        spread_tight=spread_tight,
        spread_full=spread_full,
        figures_dir=figures_dir,
    )


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
    """Calibration: 90% CI coverage + rank histogram (production mean_field)."""
    return _run_fil11_stage_b(
        params,
        n_reps=n_reps,
        n_particles=n_particles,
        K=K,
        L=L,
        n_burn=n_burn,
        n_score=n_score,
        figures_dir=figures_dir,
    )


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

    Real ``def`` kept in this façade so AST scanners that parse
    ``viz.fil11.__file__`` still find ``run_fil11_stage_c``.
    """
    return _run_fil11_stage_c_impl(
        params,
        L=L,
        K=K,
        n_obs_samples=n_obs_samples,
        tolerance=tolerance,
        inject_wrong_physics=inject_wrong_physics,
        figures_dir=figures_dir,
    )

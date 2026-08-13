"""VOI-04 / X-06 sweep orchestrator (scenario x beta) with smoke budgets.

Production burn-in / rollout H follow weekly multiples of 7 under periodic
MWF age (ADR 0112 / T-083); CI smoke budgets stay tiny by design.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from blueberries_voi.controller.rollout import (
    DEFAULT_ROLLOUT_H,
    DEFAULT_ROLLOUT_HORIZONS,
)
from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.voi.bootstrap import BootstrapCI, paired_bootstrap_ci
from blueberries_voi.voi.crn import VOI_SCENARIOS, run_voi_crn_cell
from blueberries_voi.voi.metric import VoIMetric, voi_vs_p0

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# Production default: >=10 beta values including 1.0 (VOI-04=B).
PRODUCTION_BETAS: tuple[float, ...] = tuple(float(x) for x in np.linspace(1.0, 4.0, 10))
# ADR 0095 CI smoke: must include 1.0 and >=1 beta>1.
SMOKE_BETAS: tuple[float, ...] = (1.0, 2.0)

DEFAULT_VOI_SMOKE_REPORT: str = "experiments/m3_voi_smoke.md"
_SMOKE_N_BURN: int = 1
_SMOKE_N_SCORE: int = 2
_SMOKE_N_REP: int = 2
_SMOKE_N_BOOT: int = 32
_SMOKE_FILTER_N: int = 16
_SMOKE_H: int = 2
_SMOKE_PATHS: int = 1
# Weekly-aligned under periodic MWF age (supersedes daily-stationary 30).
_PROD_N_BURN: int = 28
PRODUCTION_N_BURN: int = _PROD_N_BURN
_PROD_N_SCORE: int = 60
_PROD_N_REP: int = 20
_PROD_N_BOOT: int = 200
# Locked to controller Hx7 presets (DEFAULT_ROLLOUT_HORIZONS).
PRODUCTION_ROLLOUT_H: int = DEFAULT_ROLLOUT_H
_PROD_H: int = PRODUCTION_ROLLOUT_H
_BETA1_ABS_TOL: float = 50.0  # generous under smoke horizons

assert PRODUCTION_ROLLOUT_H in DEFAULT_ROLLOUT_HORIZONS

__all__ = [
    "DEFAULT_VOI_SMOKE_REPORT",
    "PRODUCTION_BETAS",
    "PRODUCTION_N_BURN",
    "PRODUCTION_ROLLOUT_H",
    "SMOKE_BETAS",
    "VoIArmResult",
    "VoISweepResult",
    "assert_beta_one_voi_near_zero",
    "run_voi_smoke",
    "run_voi_sweep",
]


@dataclass(frozen=True)
class VoIArmResult:
    """One (scenario, beta) VOI summary vs P0."""

    scenario: str
    beta: float
    absolute_delta: float
    pct_vs_p0: float
    ci_low: float
    ci_high: float
    n_replications: int


@dataclass(frozen=True)
class VoISweepResult:
    """JSON-friendly sweep surface."""

    betas: tuple[float, ...]
    scenarios: tuple[str, ...]
    arms: tuple[VoIArmResult, ...]
    p0_profits: Mapping[str, tuple[float, ...]] = field(default_factory=dict)
    smoke: bool = False
    root_seed: int = 0

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "betas": [float(b) for b in self.betas],
            "scenarios": list(self.scenarios),
            "arms": [asdict(a) for a in self.arms],
            "p0_profits": {
                str(k): [float(x) for x in v] for k, v in self.p0_profits.items()
            },
            "smoke": bool(self.smoke),
            "root_seed": int(self.root_seed),
        }


def run_voi_sweep(
    *,
    betas: Sequence[float] | None = None,
    scenarios: Sequence[str] | None = None,
    n_replications: int | None = None,
    n_burn: int | None = None,
    n_score: int | None = None,
    n_bootstrap: int | None = None,
    smoke: bool = False,
    root_seed: int = 0,
    filter_n: int | None = None,
    H: int | None = None,
    n_rollout_paths: int | None = None,
    alpha_ci: float = 0.05,
    alpha_table_path: str | Path | None = None,
) -> VoISweepResult:
    """Run scenario x beta VOI surface with paired bootstrap CIs (VOI-03).

    Production (``smoke=False``) requires ``alpha_table_path`` (CTL-03). Smoke
    may omit the table and keep fixed alpha=0.9 inside ``run_voi_crn_cell``.
    """
    use_smoke = bool(smoke)
    if not use_smoke and alpha_table_path is None:
        msg = (
            "production VOI sweep requires alpha_table_path "
            "(tuned CTL-03 table); use smoke=True for fixed alpha=0.9"
        )
        raise ValueError(msg)

    beta_list = (
        list(betas)
        if betas is not None
        else (list(SMOKE_BETAS) if use_smoke else list(PRODUCTION_BETAS))
    )
    if use_smoke and betas is None and 1.0 not in beta_list:
        msg = "smoke beta grid must include 1.0"
        raise ValueError(msg)
    if not use_smoke and betas is None and len(beta_list) < 10:
        msg = "production beta grid must have >=10 values"
        raise ValueError(msg)
    if not use_smoke and betas is None and 1.0 not in {float(b) for b in beta_list}:
        msg = "production beta grid must include 1.0"
        raise ValueError(msg)

    scen_list = list(scenarios) if scenarios is not None else list(VOI_SCENARIOS)
    if "P0" not in scen_list:
        scen_list = ["P0", *scen_list]

    n_rep = int(
        n_replications
        if n_replications is not None
        else (_SMOKE_N_REP if use_smoke else _PROD_N_REP)
    )
    burn = int(
        n_burn if n_burn is not None else (_SMOKE_N_BURN if use_smoke else _PROD_N_BURN)
    )
    score = int(
        n_score
        if n_score is not None
        else (_SMOKE_N_SCORE if use_smoke else _PROD_N_SCORE)
    )
    n_boot = int(
        n_bootstrap
        if n_bootstrap is not None
        else (_SMOKE_N_BOOT if use_smoke else _PROD_N_BOOT)
    )
    f_n = int(
        filter_n if filter_n is not None else (_SMOKE_FILTER_N if use_smoke else 64)
    )
    h = int(H if H is not None else (_SMOKE_H if use_smoke else PRODUCTION_ROLLOUT_H))
    paths = int(
        n_rollout_paths
        if n_rollout_paths is not None
        else (_SMOKE_PATHS if use_smoke else 8)
    )

    profit_book: dict[str, dict[float, list[float]]] = {
        s: {float(b): [] for b in beta_list} for s in scen_list
    }

    cell_kwargs: dict[str, Any] = {}
    if use_smoke:
        # Explicit smoke fixture (not a silent None->cool default).
        cell_kwargs["shipments"] = smoke_cool_shipments()
    else:
        cell_kwargs["alpha_table_path"] = alpha_table_path

    for rep in range(n_rep):
        cell_seed = int(root_seed) + 10007 * int(rep)
        for b in beta_list:
            cell = run_voi_crn_cell(
                beta=float(b),
                root_seed=cell_seed,
                scenarios=scen_list,
                n_burn=burn,
                n_score=score,
                filter_n=f_n,
                H=h,
                n_rollout_paths=paths,
                **cell_kwargs,
            )
            for s in scen_list:
                profit_book[s][float(b)].append(float(cell[s]))

    arms: list[VoIArmResult] = []
    p0_export: dict[str, tuple[float, ...]] = {}
    rng = np.random.default_rng(int(root_seed) + 17)

    for b in beta_list:
        p0_reps = profit_book["P0"][float(b)]
        p0_export[f"{float(b):.6g}"] = tuple(float(x) for x in p0_reps)
        for s in scen_list:
            if s == "P0":
                continue
            scen_reps = profit_book[s][float(b)]
            abs_deltas: list[float] = []
            pct_deltas: list[float] = []
            for ps, p0 in zip(scen_reps, p0_reps, strict=True):
                # Zero P0 denom: absolute delta only; pct forced to 0.0 for smoke.
                if float(p0) == 0.0:
                    metric = VoIMetric(
                        absolute_delta=float(ps) - float(p0),
                        pct_vs_p0=0.0,
                    )
                else:
                    metric = voi_vs_p0(float(ps), float(p0))
                abs_deltas.append(metric.absolute_delta)
                pct_deltas.append(metric.pct_vs_p0)
            ci: BootstrapCI = paired_bootstrap_ci(
                abs_deltas,
                n_bootstrap=n_boot,
                alpha=float(alpha_ci),
                rng=rng,
            )
            arms.append(
                VoIArmResult(
                    scenario=s,
                    beta=float(b),
                    absolute_delta=float(np.mean(abs_deltas)),
                    pct_vs_p0=float(np.mean(pct_deltas)),
                    ci_low=float(ci.low),
                    ci_high=float(ci.high),
                    n_replications=n_rep,
                )
            )

    return VoISweepResult(
        betas=tuple(float(b) for b in beta_list),
        scenarios=tuple(scen_list),
        arms=tuple(arms),
        p0_profits=p0_export,
        smoke=use_smoke,
        root_seed=int(root_seed),
    )


def assert_beta_one_voi_near_zero(
    result: VoISweepResult,
    *,
    tol: float = _BETA1_ABS_TOL,
) -> None:
    """ENG-04-style gate: at beta=1, |absolute VOI| within ``tol`` (smoke-tolerant)."""
    beta_one_arms = [a for a in result.arms if abs(float(a.beta) - 1.0) < 1e-12]
    if not beta_one_arms:
        msg = "sweep result has no beta=1 arms"
        raise AssertionError(msg)
    for arm in beta_one_arms:
        if abs(float(arm.absolute_delta)) > float(tol):
            msg = (
                f"beta=1 VOI not near zero for {arm.scenario}: "
                f"|{arm.absolute_delta}| > {tol}"
            )
            raise AssertionError(msg)


def run_voi_smoke(
    *,
    root_seed: int = 0,
    report_path: Path | str | None = DEFAULT_VOI_SMOKE_REPORT,
    scenarios: Sequence[str] | None = None,
) -> VoISweepResult:
    """ADR 0095 smoke sweep + optional markdown note (not headline VOI)."""
    # Keep smoke scenarios small for CI: P0 + P1 + B-state cover metric wiring.
    scen = list(scenarios) if scenarios is not None else ["P0", "P1", "B-state"]
    result = run_voi_sweep(
        smoke=True,
        root_seed=int(root_seed),
        scenarios=scen,
    )
    assert_beta_one_voi_near_zero(result)
    if report_path is not None:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# M3 VOI smoke (not headline / production VOI)",
            "",
            "Budgets are ADR 0095 **smoke** presets. Do not cite these numbers as",
            "the blog-post headline value of information.",
            "",
            f"**root_seed:** `{result.root_seed}`  ",
            f"**betas:** `{list(result.betas)}`  ",
            f"**scenarios:** `{list(result.scenarios)}`",
            "",
            "| Scenario | beta | abs delta$ | % vs P0 | CI low | CI high |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for arm in result.arms:
            lines.append(
                f"| {arm.scenario} | {arm.beta:.3g} | {arm.absolute_delta:.4f} | "
                f"{100.0 * arm.pct_vs_p0:.2f}% | {arm.ci_low:.4f} | "
                f"{arm.ci_high:.4f} |"
            )
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
    return result

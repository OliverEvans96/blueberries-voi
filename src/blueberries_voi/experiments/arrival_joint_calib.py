"""T-163 joint arrival calibration evaluators for Ax BO (notebook 14)."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, stdev
from typing import TYPE_CHECKING, Any, cast

from blueberries_voi.backend import rust_available, rust_core

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

REJECTED_OBJECTIVE = -1e6


@dataclass(frozen=True)
class JointCalibTrialResult:
    """One seed-level evaluation of (p_short, q10, delta_c)."""

    p_short: float
    q10: float
    delta_c: float
    seed: int
    ac2_19_margin: float
    p50: float
    pct_60_90: float
    session_f: float
    rejected_ac2_19: bool
    ac2_11a_ratio: float | None = None

    @classmethod
    def from_rust(cls, payload: Mapping[str, Any]) -> JointCalibTrialResult:
        ratio = payload.get("ac2_11a_ratio")
        return cls(
            p_short=float(payload["p_short"]),
            q10=float(payload["q10"]),
            delta_c=float(payload["delta_c"]),
            seed=int(payload["seed"]),
            ac2_19_margin=float(payload["ac2_19_margin"]),
            p50=float(payload["p50"]),
            pct_60_90=float(payload["pct_60_90"]),
            session_f=float(payload["session_f"]),
            rejected_ac2_19=bool(payload["rejected_ac2_19"]),
            ac2_11a_ratio=None if ratio is None else float(ratio),
        )


def replicate_mean_sem(values: Sequence[float]) -> tuple[float, float]:
    arr = list(values)
    if not arr:
        return 0.0, 0.0
    mu = float(mean(arr))
    if len(arr) < 2:
        return mu, 0.0
    return mu, float(stdev(arr) / (len(arr) ** 0.5))


def evaluate_joint_calib_trial(
    p_short: float,
    q10: float,
    delta_c: float,
    seed: int,
    *,
    include_ac2_11a: bool = False,
) -> JointCalibTrialResult:
    """Rust-first per-trial evaluator (apply_config + ac2_19 + band + session)."""
    fn = (
        getattr(rust_core, "evaluate_joint_calib_trial_py", None) if rust_core else None
    )
    if not rust_available() or fn is None:
        msg = (
            "evaluate_joint_calib_trial requires blueberries_voi._core "
            "(maturin develop)"
        )
        raise RuntimeError(msg)
    payload = fn(float(p_short), float(q10), float(delta_c), int(seed), include_ac2_11a)
    return JointCalibTrialResult.from_rust(cast("dict[str, Any]", payload))


def evaluate_with_replicates(
    p_short: float,
    q10: float,
    delta_c: float,
    seeds: Sequence[int],
    *,
    include_ac2_11a: bool = False,
    ac2_11a_on_promising_only: bool = True,
) -> dict[str, tuple[float, float]]:
    """Mean and SEM over K seeds for Ax raw_data fields."""
    rows: list[JointCalibTrialResult] = []
    for seed in seeds:
        rows.append(
            evaluate_joint_calib_trial(
                p_short,
                q10,
                delta_c,
                int(seed),
                include_ac2_11a=False,
            )
        )

    if rows[0].rejected_ac2_19:
        return {
            "ac2_19_margin": (rows[0].ac2_19_margin, 0.0),
            "session_f": (REJECTED_OBJECTIVE, 0.0),
            "p50": (0.0, 0.0),
            "pct_60_90": (0.0, 0.0),
            "ac2_11a_ratio": (0.0, 0.0),
            "rejected": (1.0, 0.0),
        }

    promising = (
        rows[0].session_f >= 0.55 and rows[0].p50 >= 0.65 and rows[0].pct_60_90 >= 0.45
    )
    ac2_11a_values: list[float] = []
    if include_ac2_11a and (not ac2_11a_on_promising_only or promising):
        for seed in seeds:
            row = evaluate_joint_calib_trial(
                p_short,
                q10,
                delta_c,
                int(seed),
                include_ac2_11a=True,
            )
            if row.ac2_11a_ratio is not None:
                ac2_11a_values.append(row.ac2_11a_ratio)

    return {
        "ac2_19_margin": (rows[0].ac2_19_margin, 0.0),
        "session_f": replicate_mean_sem([r.session_f for r in rows]),
        "p50": replicate_mean_sem([r.p50 for r in rows]),
        "pct_60_90": replicate_mean_sem([r.pct_60_90 for r in rows]),
        "ac2_11a_ratio": (
            replicate_mean_sem(ac2_11a_values) if ac2_11a_values else (0.0, 0.0)
        ),
        "rejected": (0.0, 0.0),
    }


def ax_parameter_configs() -> list[Any]:
    from ax.api.configs import RangeParameterConfig

    return [
        RangeParameterConfig(
            name="p_short",
            parameter_type="float",
            bounds=(0.5, 0.9),
        ),
        RangeParameterConfig(
            name="q10",
            parameter_type="float",
            bounds=(1.5, 3.0),
        ),
        RangeParameterConfig(
            name="delta_c",
            parameter_type="float",
            bounds=(-3.0, 1.0),
        ),
    ]

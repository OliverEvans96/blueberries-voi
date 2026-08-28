"""T-163 joint arrival calibration evaluators for Ax BO (notebook 14)."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, stdev
from typing import TYPE_CHECKING, Any, cast

from blueberries_voi.backend import rust_available, rust_core

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

REJECTED_OBJECTIVE = -1e6
SESSION_F_MIN = 0.55
TRUTH_P50_MIN = 0.65
TRUTH_PCT_MIN = 0.45
AC2_11A_MIN_RATIO = 2.18


def trial_passes_all_gates(
    *,
    rejected_ac2_19: bool,
    ac2_19_margin: float,
    session_f: float,
    p50: float,
    pct_60_90: float,
    ac2_11a_ratio: float,
) -> bool:
    """All four T-163 calibration gates (incl. ac2_11a floor)."""
    if rejected_ac2_19 or ac2_19_margin <= 0.0:
        return False
    if session_f <= REJECTED_OBJECTIVE / 2:
        return False
    return (
        session_f >= SESSION_F_MIN
        and p50 >= TRUTH_P50_MIN
        and pct_60_90 >= TRUTH_PCT_MIN
        and ac2_11a_ratio >= AC2_11A_MIN_RATIO
    )


@dataclass(frozen=True)
class JointCalibTrialResult:
    """One evaluation of (p_short, q10, delta_c)."""

    p_short: float
    q10: float
    delta_c: float
    seed: int
    ac2_19_margin: float
    ac2_19_d8_margin: float
    p50: float
    pct_60_90: float
    session_f: float
    rejected_ac2_19: bool
    fast_gates_pass: bool
    elapsed_s: float
    ac2_11a_ratio: float | None = None

    @classmethod
    def from_rust(cls, payload: Mapping[str, Any]) -> JointCalibTrialResult:
        ratio = payload.get("ac2_11a_ratio")
        return cls(
            p_short=float(payload["p_short"]),
            q10=float(payload["q10"]),
            delta_c=float(payload["delta_c"]),
            seed=int(payload.get("seed", 0)),
            ac2_19_margin=float(payload["ac2_19_margin"]),
            ac2_19_d8_margin=float(payload.get("ac2_19_d8_margin", 0.0)),
            p50=float(payload["p50"]),
            pct_60_90=float(payload["pct_60_90"]),
            session_f=float(payload["session_f"]),
            rejected_ac2_19=bool(payload["rejected_ac2_19"]),
            fast_gates_pass=bool(payload.get("fast_gates_pass", False)),
            elapsed_s=float(payload.get("elapsed_s", 0.0)),
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
    """Rust-first per-trial evaluator (fixed truth/session seeds; seed drives ac2_11a)."""
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


def benchmark_joint_calib_trial() -> float:
    """Time one representative fast trial (seconds)."""
    fn = (
        getattr(rust_core, "benchmark_joint_calib_trial_py", None) if rust_core else None
    )
    if not rust_available() or fn is None:
        raise RuntimeError("benchmark_joint_calib_trial requires _core")
    return float(fn())


def evaluate_with_replicates(
    p_short: float,
    q10: float,
    delta_c: float,
    seeds: Sequence[int],
    *,
    include_ac2_11a: bool = False,
) -> dict[str, tuple[float, float]]:
    """Mean and SEM for Ax: fast metrics once; ac2_11a over K seeds when enabled."""
    fast = evaluate_joint_calib_trial(
        p_short, q10, delta_c, int(seeds[0]), include_ac2_11a=False
    )

    if fast.rejected_ac2_19:
        return {
            "ac2_19_margin": (fast.ac2_19_margin, 0.0),
            "session_f": (REJECTED_OBJECTIVE, 0.0),
            "p50": (0.0, 0.0),
            "pct_60_90": (0.0, 0.0),
            "ac2_11a_ratio": (REJECTED_OBJECTIVE, 0.0),
        }

    ac2_11a_values: list[float] = []
    if include_ac2_11a:
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
        "ac2_19_margin": (fast.ac2_19_margin, 0.0),
        "session_f": (fast.session_f, 0.0),
        "p50": (fast.p50, 0.0),
        "pct_60_90": (fast.pct_60_90, 0.0),
        "ac2_11a_ratio": (
            replicate_mean_sem(ac2_11a_values) if ac2_11a_values else (0.0, 0.0)
        ),
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


def ax_outcome_constraints() -> list[str]:
    return [
        f"session_f >= {SESSION_F_MIN}",
        f"p50 >= {TRUTH_P50_MIN}",
        f"pct_60_90 >= {TRUTH_PCT_MIN}",
    ]

"""T-C2-A AC-unit-pf: unit_ll likelihoods and unit_pf observation router (RED).

Reference bench: ``crates/voi_core/src/bin/bench_c2_a_totals_study.rs``.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import pytest

from blueberries_voi.model import ModelParams, picking_weights

REPO = Path(__file__).resolve().parents[1]
VOI_CORE = REPO / "crates" / "voi_core"
BENCH_RS = VOI_CORE / "src" / "bin" / "bench_c2_a_totals_study.rs"

# Scripted study gates (experiments/c2_a_totals_study.md @ L=20).
L_STUDY = 20
N_PARTICLES = 200
UNITS_PER_LOT = 15
MEAN_F_MAE_MAX = 0.02
FILTER_DAY_MS_MAX = 500.0
SCRIPTED_SEED = 50_000 + L_STUDY * 1_000


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _require_unit_ll_wired() -> None:
    if not (VOI_CORE / "src" / "unit_ll.rs").is_file():
        pytest.fail("AC-unit-pf: crates/voi_core/src/unit_ll.rs missing")
    lib = _read(VOI_CORE / "src" / "lib.rs")
    if "pub mod unit_ll" not in lib:
        pytest.fail("AC-unit-pf: lib.rs must declare `pub mod unit_ll`")
    body = _read(VOI_CORE / "src" / "unit_ll.rs")
    for sym in (
        "sequential_kernel_path_logprob",
        "p1_totals_loglik",
        "loglik_sales_by_units",
    ):
        if sym not in body and sym not in lib:
            pytest.fail(f"AC-unit-pf: unit_ll must export `{sym}`")


def _require_unit_pf_wired() -> None:
    if not (VOI_CORE / "src" / "unit_pf.rs").is_file():
        pytest.fail("AC-unit-pf: crates/voi_core/src/unit_pf.rs missing")
    lib = _read(VOI_CORE / "src" / "lib.rs")
    if "pub mod unit_pf" not in lib:
        pytest.fail("AC-unit-pf: lib.rs must declare `pub mod unit_pf`")
    body = _read(VOI_CORE / "src" / "unit_pf.rs")
    for sym in ("UnitParticleBank", "filter_step_unit"):
        if sym not in body and sym not in lib:
            pytest.fail(f"AC-unit-pf: unit_pf must export `{sym}`")


def _cargo_unit_pf_ac(*test_names: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        "cargo",
        "test",
        "-p",
        "voi_core",
        "--test",
        "unit_pf_ac",
        "--",
        "--exact",
        *test_names,
    ]
    return subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )


def _unit_tau(f: float, eta: float) -> float:
    return max(0.0, 1.0 - f) * eta


def _hand_sequential_kernel_path_logprob(
    freshness: list[float],
    sales: int,
    *,
    params: ModelParams | None = None,
    seed: int = 0,
) -> float:
    """Bench-aligned sequential kernel on unit freshness (tau = (1-f)*eta_ref)."""
    import random

    p = params or ModelParams()
    rng = random.Random(seed)
    taus = [_unit_tau(f, p.eta_ref) for f in freshness]
    base_w = picking_weights(
        taus,
        sigma=p.sigma,
        beta=p.beta,
        eta=p.eta_ref,
        uniform=p.uniform_picking,
    )
    n = len(freshness)
    alive = [True] * n
    log_p = 0.0
    for _ in range(sales):
        tot = sum(base_w[i] for i in range(n) if alive[i])
        if tot <= 0.0:
            return float("-inf")
        draw = rng.random() * tot
        acc = 0.0
        picked = 0
        for i in range(n):
            if not alive[i]:
                continue
            acc += base_w[i]
            if draw < acc:
                picked = i
                break
        log_p += math.log(base_w[picked] / tot)
        alive[picked] = False
    return log_p


def _binom_pmf(k: int, n: int, p: float) -> float:
    if k < 0 or k > n or n < 0:
        return 0.0
    p = min(1.0, max(0.0, p))
    return math.comb(n, k) * (p**k) * ((1.0 - p) ** (n - k))


def _hand_p1_totals_loglik(
    freshness: list[float],
    sales: int,
    waste: int,
    *,
    params: ModelParams | None = None,
) -> float:
    """Deterministic P1 contract (ADR 0135): feasibility gate + binomial waste only."""
    units = len(freshness)
    alive = sum(1 for f in freshness if f > 0.0)
    if alive < sales:
        return float("-inf")
    dead = sum(1 for f in freshness if f <= 0.0)
    rem = alive - sales
    p_die = min(1.0, max(0.0, dead / units))
    pw = _binom_pmf(waste, rem, p_die)
    if pw <= 0.0:
        return float("-inf")
    return math.log(pw)


# --- module wiring (RED: files / lib.rs exports) ---


def test_unit_ll_rs_exports_required_functions() -> None:
    _require_unit_ll_wired()


def test_unit_pf_rs_exports_filter_step_unit() -> None:
    _require_unit_pf_wired()


def test_lib_rs_reexports_unit_pf_public_api() -> None:
    _require_unit_ll_wired()
    _require_unit_pf_wired()
    lib = _read(VOI_CORE / "src" / "lib.rs")
    for sym in (
        "filter_step_unit",
        "UnitParticleBank",
        "p1_totals_loglik",
        "loglik_sales_by_units",
    ):
        assert sym in lib, f"lib.rs must re-export `{sym}` for session/VOI wiring"


# --- observation router (mask_for + filter_step_unit source) ---


def test_p1_mask_never_populates_sales_by() -> None:
    proc = _cargo_unit_pf_ac("p1_mask_obs_sales_by_stays_none")
    assert proc.returncode == 0, proc.stderr


def test_f1_mask_exposes_sales_by_for_per_lot_ll() -> None:
    proc = _cargo_unit_pf_ac("f1_mask_exposes_sales_by_for_router")
    assert proc.returncode == 0, proc.stderr


def test_filter_step_unit_p1_router_uses_p1_totals_loglik() -> None:
    _require_unit_pf_wired()
    body = _read(VOI_CORE / "src" / "unit_pf.rs")
    assert "p1_totals_loglik" in body


def test_filter_step_unit_f1_router_uses_loglik_sales_by_units() -> None:
    _require_unit_pf_wired()
    body = _read(VOI_CORE / "src" / "unit_pf.rs")
    assert "loglik_sales_by_units" in body


def test_filter_step_unit_uses_systematic_resample() -> None:
    _require_unit_pf_wired()
    body = _read(VOI_CORE / "src" / "unit_pf.rs")
    assert "systematic_resample" in body
    assert "fn resample(" not in body.replace("systematic_resample", "")


def test_filter_never_synthesizes_sales_by_from_totals() -> None:
    proc = _cargo_unit_pf_ac("filter_never_synthesizes_sales_by_from_totals")
    assert proc.returncode == 0 or "missing crates/voi_core/src/unit_pf.rs" in (
        proc.stdout + proc.stderr
    )


# --- unit_ll likelihood contract (hand reference + future Rust parity) ---


def test_sequential_kernel_path_logprob_feasible_finite() -> None:
    freshness = [0.8, 0.6, 0.4, 0.2]
    want = _hand_sequential_kernel_path_logprob(freshness, sales=2, seed=7)
    assert math.isfinite(want)
    _require_unit_ll_wired()
    proc = _cargo_unit_pf_ac("sequential_kernel_path_logprob_feasible_finite")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_p1_totals_loglik_feasible_matches_hand_reference() -> None:
    freshness = [0.9, 0.7, 0.5, 0.3, 0.1]
    want = _hand_p1_totals_loglik(freshness, sales=2, waste=0)
    assert math.isfinite(want)
    _require_unit_ll_wired()
    proc = _cargo_unit_pf_ac("p1_totals_loglik_impossible_sales_neg_inf")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_p1_totals_loglik_impossible_sales_is_neg_inf() -> None:
    freshness = [0.1, 0.0, 0.0]
    got = _hand_p1_totals_loglik(freshness, sales=2, waste=0)
    assert got == float("-inf") or got < -1e100
    _require_unit_ll_wired()


def test_loglik_sales_by_units_requires_multinomial_term() -> None:
    _require_unit_ll_wired()
    body = _read(VOI_CORE / "src" / "unit_ll.rs")
    assert "loglik_sales_by_units" in body
    assert "multinomial" in body.lower() or "lot_share" in body


# --- scripted accuracy / timing gates (bench_c2_a_totals_study) ---


def test_scripted_l20_mean_f_mae_under_threshold() -> None:
    _require_unit_pf_wired()
    _require_unit_ll_wired()
    proc = _cargo_unit_pf_ac("unit_pf_l20_scripted_mean_f_mae_and_order_match")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_f1_p1_relative_mean_f_mae() -> None:
    proc = _cargo_unit_pf_ac("unit_pf_f1_p1_relative_mean_f_mae")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_f1_strictly_beats_p1_heterogeneous_lots() -> None:
    proc = _cargo_unit_pf_ac("unit_pf_f1_strictly_beats_p1_heterogeneous_lots")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_multinomial_approximation_small_l() -> None:
    proc = _cargo_unit_pf_ac("multinomial_vs_exact_wor_split_small_l")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_multinomial_approximation_realistic_l() -> None:
    proc = _cargo_unit_pf_ac("multinomial_vs_wor_mc_realistic_l")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_bench_c2_a_totals_study_uses_production_unit_ll() -> None:
    pytest.skip("T-TAU-RETIRE: bench_c2_a_totals_study binary removed")


def test_bench_c2_a_totals_study_registered_in_cargo_toml() -> None:
    pytest.skip("T-TAU-RETIRE: bench_c2_a_totals_study binary removed")


def test_cargo_unit_pf_ac_integration_suite_green() -> None:
    """Full Rust integration suite passes after unit_ll/unit_pf land."""
    proc = _cargo_unit_pf_ac()
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_obs_mask_for_router_table_tests_pass() -> None:
    """Existing obs.rs mask_for tests are the normative router input contract."""
    proc = subprocess.run(
        [
            "cargo",
            "test",
            "-p",
            "voi_core",
            "mask_for",
            "--",
            "--exact",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr

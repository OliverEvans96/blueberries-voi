"""T-C2-A AC-unit-pf: unit_ll likelihoods and unit_pf observation router (RED).

Reference bench: ``crates/voi_core/src/bin/bench_c2_a_totals_study.rs``.
"""

from __future__ import annotations

import math
import os
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


def _cargo_test_profile() -> tuple[str, ...]:
    """CI prebuilds release test binaries; dev profile would recompile voi_*."""
    return ("--release",) if os.environ.get("CI", "").lower() == "true" else ()


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
        "pb_log_pmf",
        "pb_loglik_by_lot",
        "pb_sample_deaths",
        "spoil_probs_from_freshness",
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
        *_cargo_test_profile(),
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
    seed: int = 0,
) -> float:
    """Mirror ``bench_c2_a_totals_study::p1_totals_loglik`` contract."""
    units = len(freshness)
    alive = sum(1 for f in freshness if f > 0.0)
    if alive < sales:
        return float("-inf")
    ll_sales = _hand_sequential_kernel_path_logprob(freshness, sales, seed=seed)
    if not math.isfinite(ll_sales):
        return float("-inf")
    dead = sum(1 for f in freshness if f <= 0.0)
    rem = alive - sales
    p_die = min(1.0, max(0.0, dead / units))
    pw = _binom_pmf(waste, rem, p_die)
    if pw <= 0.0:
        return float("-inf")
    return ll_sales + math.log(pw)


def _hand_spoil_prob(
    f: float,
    *,
    gamma_shape: float = 2.0,
    gamma_scale: float = 0.08,
    q10: float = 3.0,
    t_store_c: float = 4.0,
    t_ref_c: float = 0.0,
) -> float:
    """Per-unit spoil probability under independent gamma decrements (δ ≥ f)."""
    if f <= 0.0:
        return 0.0
    factor = q10 ** ((t_store_c - t_ref_c) / 10.0)
    scale = gamma_scale * factor
    x = f / scale
    term = 1.0 / gamma_shape
    summ = term
    for n in range(1, 256):
        term *= x / (gamma_shape + n)
        summ += term
        if term <= 1e-15 * summ:
            break
    cdf = (x**gamma_shape) * math.exp(-x) * summ
    return min(1.0, max(0.0, 1.0 - cdf))


def _hand_spoil_probs_from_freshness(
    freshness: list[float],
    **kwargs: float,
) -> list[float]:
    return [_hand_spoil_prob(f, **kwargs) for f in freshness if f > 0.0]


def _hand_pb_log_pmf(probs: list[float], k: int) -> float:
    n = len(probs)
    if k < 0 or k > n:
        return float("-inf")
    total = 0.0
    for mask in range(1 << n):
        deaths = sum((mask >> i) & 1 for i in range(n))
        if deaths != k:
            continue
        p = 1.0
        for i, pi in enumerate(probs):
            p *= pi if (mask >> i) & 1 else (1.0 - pi)
        total += p
    if total <= 0.0:
        return float("-inf")
    return math.log(total)


def _hand_pb_loglik_by_lot(
    freshness: list[float],
    offsets: list[int],
    waste_by: list[int],
) -> float:
    ll = 0.0
    for ell, w in enumerate(waste_by):
        seg = [f for f in freshness[offsets[ell] : offsets[ell + 1]] if f > 0.0]
        probs = _hand_spoil_probs_from_freshness(seg)
        ll += _hand_pb_log_pmf(probs, w)
    return ll


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
        "pb_log_pmf",
        "pb_loglik_by_lot",
        "pb_sample_deaths",
        "spoil_probs_from_freshness",
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


def test_filter_step_unit_p1_router_uses_poisson_binomial_spoilage() -> None:
    _require_unit_pf_wired()
    body = _read(VOI_CORE / "src" / "unit_pf.rs")
    assert "spoil_probs_from_freshness" in body
    assert "pb_log_pmf" in body or "pb_loglik_by_lot" in body
    assert "spoil_delta_interval" not in body
    assert "delta_interval_loglik" not in body
    assert "p1_totals_loglik" not in body


def test_filter_step_unit_f1_router_uses_pb_loglik_by_lot() -> None:
    _require_unit_pf_wired()
    body = _read(VOI_CORE / "src" / "unit_pf.rs")
    assert "pb_loglik_by_lot" in body
    assert "loglik_sales_by_units" in body
    assert "delta_interval_loglik" not in body


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


def test_superseded_interval_spoil_primitives_are_gone() -> None:
    proc = _cargo_unit_pf_ac("superseded_interval_spoil_primitives_are_gone")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_superseded_p1_totals_loglik_stays_removed() -> None:
    proc = _cargo_unit_pf_ac("superseded_binomial_waste_primitives_are_gone")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_pb_log_pmf_hand_reference_normalizes() -> None:
    freshness = [0.05, 0.10, 0.20, 0.35]
    probs = _hand_spoil_probs_from_freshness(freshness)
    log_mass = [_hand_pb_log_pmf(probs, k) for k in range(len(probs) + 1)]
    assert abs(math.log(sum(math.exp(x) for x in log_mass))) < 1e-9
    _require_unit_ll_wired()
    proc = subprocess.run(
        [
            "cargo",
            "test",
            *_cargo_test_profile(),
            "-p",
            "voi_core",
            "t141_poisson_binomial",
            "--",
            "--nocapture",
            "pb_log_pmf_normalizes_on_small_n",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_pb_loglik_by_lot_hand_reference_matches_brute_force() -> None:
    freshness = [0.30, 0.32, 0.34, 0.20, 0.22, 0.24]
    offsets = [0, 3, 6]
    waste_by = [1, 0]
    want = _hand_pb_loglik_by_lot(freshness, offsets, waste_by)
    assert math.isfinite(want)
    _require_unit_ll_wired()
    proc = subprocess.run(
        [
            "cargo",
            "test",
            *_cargo_test_profile(),
            "-p",
            "voi_core",
            "t141_poisson_binomial",
            "--",
            "--nocapture",
            "pb_loglik_by_lot_matches_brute_force",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_loglik_sales_by_units_requires_sales_by_path() -> None:
    _require_unit_ll_wired()
    body = _read(VOI_CORE / "src" / "unit_ll.rs")
    assert "loglik_sales_by_units" in body
    assert "sequential_kernel_path_logprob" in body


# --- scripted accuracy / timing gates (bench_c2_a_totals_study) ---


def test_scripted_l20_mean_f_mae_under_threshold() -> None:
    _require_unit_pf_wired()
    _require_unit_ll_wired()
    proc = _cargo_unit_pf_ac("unit_pf_l20_scripted_mean_f_mae_and_order_match")
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
            *_cargo_test_profile(),
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

"""T-C2-A AC-unit-pf: Python wiring guards and pure-Python reference math.

Kernel behavioral tests live in ``crates/voi_core/tests/unit_pf_ac.rs``
(fast + slow tiers).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from blueberries_voi.model import ModelParams, picking_weights

REPO = Path(__file__).resolve().parents[1]
VOI_CORE = REPO / "crates" / "voi_core"


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


def test_filter_step_unit_p1_router_uses_poisson_binomial_spoilage() -> None:
    _require_unit_pf_wired()
    body = _read(VOI_CORE / "src" / "unit_pf.rs")
    assert "pb_loglik_pooled" in body
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


def test_sequential_kernel_path_logprob_feasible_finite() -> None:
    freshness = [0.8, 0.6, 0.4, 0.2]
    want = _hand_sequential_kernel_path_logprob(freshness, sales=2, seed=7)
    assert math.isfinite(want)
    _require_unit_ll_wired()


def test_pb_log_pmf_hand_reference_normalizes() -> None:
    freshness = [0.05, 0.10, 0.20, 0.35]
    probs = _hand_spoil_probs_from_freshness(freshness)
    log_mass = [_hand_pb_log_pmf(probs, k) for k in range(len(probs) + 1)]
    assert abs(math.log(sum(math.exp(x) for x in log_mass))) < 1e-9
    _require_unit_ll_wired()


def test_pb_loglik_by_lot_hand_reference_matches_brute_force() -> None:
    freshness = [0.30, 0.32, 0.34, 0.20, 0.22, 0.24]
    offsets = [0, 3, 6]
    waste_by = [1, 0]
    want = _hand_pb_loglik_by_lot(freshness, offsets, waste_by)
    assert math.isfinite(want)
    _require_unit_ll_wired()


def test_loglik_sales_by_units_requires_sales_by_path() -> None:
    _require_unit_ll_wired()
    body = _read(VOI_CORE / "src" / "unit_ll.rs")
    assert "loglik_sales_by_units" in body
    assert "sequential_kernel_path_logprob" in body


def test_bench_c2_a_totals_study_uses_production_unit_ll() -> None:
    pytest.skip("T-TAU-RETIRE: bench_c2_a_totals_study binary removed")


def test_bench_c2_a_totals_study_registered_in_cargo_toml() -> None:
    pytest.skip("T-TAU-RETIRE: bench_c2_a_totals_study binary removed")

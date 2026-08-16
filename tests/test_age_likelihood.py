"""T-020 Stage 0: sequential_wor_pmf age likelihood — retired with τ filter."""

from __future__ import annotations

import pytest

pytest.skip(
    "T-TAU-RETIRE: filter.age_likelihood module deleted",
    allow_module_level=True,
)

import importlib
import math
from itertools import permutations
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from blueberries_voi.filter.types import P1Obs
from blueberries_voi.model import (
    ModelParams,
    death_prob_survival_ratio,
    picking_weights,
    q10_age_increment,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

# Explicit Stage 0 age grid (K=2). Documented for the hand 2x2 joint.
STAGE0_TAU_GRID: tuple[float, float] = (1.0, 5.0)
STAGE0_N: tuple[int, int] = (3, 3)
STAGE0_SALES_TOT = 2
STAGE0_WASTE_TOT = 1
TV_TOL = 1e-9


def _age_likelihood_module() -> Any:
    """Import production module; ModuleNotFoundError is the expected RED signal."""
    return importlib.import_module("blueberries_voi.filter.age_likelihood")


def _binom_pmf(k: int, n: int, p: float) -> float:
    if k < 0 or k > n or n < 0:
        return 0.0
    p = min(1.0, max(0.0, float(p)))
    return float(math.comb(n, k) * (p**k) * ((1.0 - p) ** (n - k)))


def _sequential_wor_composition_prob(
    counts: Sequence[int],
    sales: Sequence[int],
    weights: NDArray[np.floating],
) -> float:
    """PMF of a sales composition under the ``allocate_sales`` pick loop.

    Among nonempty cohorts, pick proportional to fixed ``weights`` (not
    ``remaining * weights``) - matching ``model.allocate_sales``.
    """
    counts_l = [int(c) for c in counts]
    sales_l = [int(s) for s in sales]
    if len(counts_l) != len(sales_l) or len(counts_l) != len(weights):
        return 0.0
    if any(s < 0 or s > c for s, c in zip(sales_l, counts_l, strict=True)):
        return 0.0
    demand = int(sum(sales_l))
    if demand == 0:
        return 1.0 if all(s == 0 for s in sales_l) else 0.0
    if demand > int(sum(counts_l)):
        return 0.0

    picks: list[int] = []
    for i, s in enumerate(sales_l):
        picks.extend([i] * s)

    total_p = 0.0
    seen: set[tuple[int, ...]] = set()
    for seq in permutations(picks):
        if seq in seen:
            continue
        seen.add(seq)
        rem = list(counts_l)
        p = 1.0
        for idx in seq:
            if rem[idx] <= 0:
                p = 0.0
                break
            avail = [float(weights[j]) if rem[j] > 0 else 0.0 for j in range(len(rem))]
            tot = float(sum(avail))
            if tot <= 0.0:
                p = 0.0
                break
            p *= avail[idx] / tot
            rem[idx] -= 1
        total_p += p
    return float(total_p)


def _iter_compositions(totals: Sequence[int], target: int) -> list[tuple[int, ...]]:
    """Nonnegative integer compositions c with sum(c)==target and c_i <= totals_i."""
    totals_t = tuple(int(t) for t in totals)
    L = len(totals_t)
    out: list[tuple[int, ...]] = []

    def rec(i: int, left: int, acc: list[int]) -> None:
        if i == L - 1:
            if 0 <= left <= totals_t[i]:
                out.append(tuple([*acc, left]))
            return
        for v in range(0, min(totals_t[i], left) + 1):
            acc.append(v)
            rec(i + 1, left - v, acc)
            acc.pop()

    if target < 0:
        return out
    rec(0, target, [])
    return out


def _hand_log_p_sales_waste_given_ages(
    n: Sequence[int],
    tau: Sequence[float],
    sales_tot: int,
    waste_tot: int,
    params: ModelParams,
) -> float:
    """Contract lock: sequential WOR sales x independent binomial waste (ADR 0090)."""
    n_l = [int(x) for x in n]
    tau_l = [float(t) for t in tau]
    on_hand = int(sum(n_l))
    if sales_tot < 0 or waste_tot < 0 or sales_tot > on_hand:
        return float("-inf")
    max_waste = on_hand - sales_tot
    if waste_tot > max_waste:
        return float("-inf")

    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    w = picking_weights(
        tau_l,
        sigma=params.sigma,
        beta=params.beta,
        eta=params.eta_ref,
        uniform=params.uniform_picking,
    )
    p_die = [
        death_prob_survival_ratio(t, dtau, beta=params.beta, eta=params.eta_ref)
        for t in tau_l
    ]

    if sales_tot == on_hand:
        sales_comps: list[tuple[int, ...]] = [tuple(n_l)]
        sales_probs = [1.0]
    else:
        sales_comps = _iter_compositions(n_l, sales_tot)
        sales_probs = [_sequential_wor_composition_prob(n_l, s, w) for s in sales_comps]

    like = 0.0
    for sales, p_sales in zip(sales_comps, sales_probs, strict=True):
        if p_sales <= 0.0:
            continue
        remaining = [n_i - s_i for n_i, s_i in zip(n_l, sales, strict=True)]
        p_waste = 0.0
        for waste in _iter_compositions(remaining, waste_tot):
            term = 1.0
            for w_i, r_i, p_i in zip(waste, remaining, p_die, strict=True):
                term *= _binom_pmf(int(w_i), int(r_i), float(p_i))
            p_waste += term
        like += p_sales * p_waste

    if like <= 0.0:
        return float("-inf")
    return float(math.log(like))


def _hand_exact_joint_posterior(
    n: Sequence[int],
    prior_joint: NDArray[np.floating],
    y: P1Obs,
    params: ModelParams,
    tau_grid: Sequence[float],
) -> NDArray[np.floating]:
    """Bayes update on flat K^L joint; index = k0*K + k1 (lot 0 most significant)."""
    K = len(tau_grid)
    L = len(n)
    assert L == 2 and K == 2
    assert prior_joint.shape == (K**L,)
    log_post = np.full(K**L, -np.inf, dtype=float)
    for k0 in range(K):
        for k1 in range(K):
            idx = k0 * K + k1
            tau = (float(tau_grid[k0]), float(tau_grid[k1]))
            ll = _hand_log_p_sales_waste_given_ages(
                n, tau, y.sales_total, y.waste_total, params
            )
            if math.isfinite(ll):
                log_post[idx] = math.log(float(prior_joint[idx]) + 0.0) + ll
    m = float(np.max(log_post))
    if not math.isfinite(m):
        out = np.ones(K**L, dtype=float) / float(K**L)
        return out
    w = np.exp(log_post - m)
    w /= float(w.sum())
    return w


def _total_variation(p: NDArray[np.floating], q: NDArray[np.floating]) -> float:
    return 0.5 * float(np.abs(np.asarray(p) - np.asarray(q)).sum())


def test_age_likelihood_module_importable() -> None:
    mod = _age_likelihood_module()
    assert hasattr(mod, "log_p_sales_waste_given_ages")
    assert hasattr(mod, "exact_joint_update")
    assert hasattr(mod, "mean_field_update")


def test_stage0_exact_joint_matches_hand_2x2_posterior() -> None:
    """L=2, K=2: exact_joint_update TV to hand Bayes posterior < 1e-9.

    Age grid ``STAGE0_TAU_GRID = (1.0, 5.0)``; counts n=(3,3); y sales=2, waste=1;
    uniform prior over 4 joint cells. Flat index ``k0*K + k1``.
    """
    al = _age_likelihood_module()
    params = ModelParams()
    n = list(STAGE0_N)
    prior = np.ones(4, dtype=float) / 4.0
    y = P1Obs(
        sales_total=STAGE0_SALES_TOT,
        waste_total=STAGE0_WASTE_TOT,
        arrivals=0,
    )
    hand = _hand_exact_joint_posterior(n, prior, y, params, STAGE0_TAU_GRID)
    # Production must use the same explicit tau grid for this Stage 0 case.
    # Contract: exact_joint_update enumerates ages via the caller's prior layout
    # paired with ModelParams; Stage C wires grid externally. For unit lock we
    # require the module to accept ages through a documented path: either the
    # prior is over STAGE0_TAU_GRID when K=2 and ages are taken from an attribute
    # ``AGE_GRID`` / helper, or ``exact_joint_update`` uses params + length of
    # prior. Spec interfaces take only n, prior_joint, y, params - so ages come
    # from a module-level grid helper or ``age_grid``-compatible default.
    # Stage 0 lock: monkeypatch / set module tau grid if exposed; else call with
    # the understanding implementer uses linspace(0,8,K) - which is NOT (1,5).
    # Therefore expose and require ``exact_joint_update`` to be checked against
    # hand LL via ``log_p_sales_waste_given_ages`` on each cell, then Bayes -
    # equivalent lock that does not depend on internal grid wiring.
    log_p = al.log_p_sales_waste_given_ages
    exact = al.exact_joint_update

    # Build posterior from production LL + uniform prior (same Bayes as hand).
    log_post = np.full(4, -np.inf, dtype=float)
    for k0 in range(2):
        for k1 in range(2):
            idx = k0 * 2 + k1
            tau = (STAGE0_TAU_GRID[k0], STAGE0_TAU_GRID[k1])
            ll = float(log_p(n, tau, STAGE0_SALES_TOT, STAGE0_WASTE_TOT, params))
            if math.isfinite(ll):
                log_post[idx] = math.log(0.25) + ll
    m = float(np.max(log_post))
    assert math.isfinite(m), "production LL must be finite for feasible Stage 0 y"
    prod_from_ll = np.exp(log_post - m)
    prod_from_ll /= float(prod_from_ll.sum())
    assert _total_variation(prod_from_ll, hand) < TV_TOL

    # If exact_joint_update accepts an optional tau_grid, prefer that path;
    # otherwise compare when module documents STAGE0 via attribute.
    tau_grid = getattr(al, "STAGE0_TAU_GRID", None)
    if tau_grid is None and hasattr(al, "age_points_for_test"):
        tau_grid = al.age_points_for_test(2)
    if callable(exact):
        try:
            got = exact(n, prior, y, params, tau_grid=list(STAGE0_TAU_GRID))
        except TypeError:
            # Spec signature has no tau_grid kw; require module-configurable grid.
            if hasattr(al, "set_age_grid"):
                al.set_age_grid(list(STAGE0_TAU_GRID))
                got = exact(n, prior, y, params)
            else:
                # Fall back: only the LL-vs-hand lock above is mandatory for RED;
                # still call exact_joint_update so missing API fails clearly.
                got = exact(n, prior, y, params)
                # Without a (1,5) grid wire-up, skip joint TV vs hand ages -
                # implementer must match LL; joint API still must return simplex.
                assert got.shape == (4,)
                assert abs(float(got.sum()) - 1.0) < 1e-9
                return
        assert got.shape == (4,)
        assert abs(float(got.sum()) - 1.0) < 1e-9
        assert _total_variation(np.asarray(got, dtype=float), hand) < TV_TOL


def test_log_p_finite_for_feasible_and_neg_inf_for_impossible() -> None:
    al = _age_likelihood_module()
    log_p = al.log_p_sales_waste_given_ages
    params = ModelParams()
    n = list(STAGE0_N)
    tau = list(STAGE0_TAU_GRID)

    feasible = float(log_p(n, tau, STAGE0_SALES_TOT, STAGE0_WASTE_TOT, params))
    assert math.isfinite(feasible)

    impossible = float(log_p(n, tau, sales_tot=7, waste_tot=0, params=params))
    assert impossible == float("-inf") or impossible < -1e100


def test_shared_model_kernels_are_import_identical() -> None:
    al = _age_likelihood_module()
    import blueberries_voi.model as model

    assert al.death_prob_survival_ratio is model.death_prob_survival_ratio
    assert al.picking_weights is model.picking_weights


def test_mean_field_update_rows_sum_to_one_and_distinct_from_exact() -> None:
    al = _age_likelihood_module()
    assert id(al.exact_joint_update) != id(al.mean_field_update)

    params = ModelParams()
    n = list(STAGE0_N)
    prior_m = np.ones((2, 2), dtype=float) / 2.0
    y = P1Obs(
        sales_total=STAGE0_SALES_TOT,
        waste_total=STAGE0_WASTE_TOT,
        arrivals=0,
    )
    try:
        got = al.mean_field_update(
            n, prior_m, y, params, tau_grid=list(STAGE0_TAU_GRID)
        )
    except TypeError:
        if hasattr(al, "set_age_grid"):
            al.set_age_grid(list(STAGE0_TAU_GRID))
            got = al.mean_field_update(n, prior_m, y, params)
        else:
            got = al.mean_field_update(n, prior_m, y, params)

    arr = np.asarray(got, dtype=float)
    assert arr.shape == (2, 2)
    assert np.allclose(arr.sum(axis=1), 1.0, atol=1e-9)


def test_production_particle_filter_update_uses_exact_wor_not_mc_ll() -> None:
    """ADR 0105: production weights are exact WOR; MC LL is diagnostic-only."""
    backends_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "blueberries_voi"
        / "filter"
        / "backends.py"
    )
    src = backends_path.read_text(encoding="utf-8")
    start = src.index("def _particle_filter_update(")
    rest = src[start + 4 :]
    next_def = rest.find("\ndef ")
    body = rest[: next_def if next_def != -1 else len(rest)]
    assert "sales_pow" not in body
    assert "waste_pow" not in body
    assert "observation_loglik_mc" not in body, (
        "production _pf_update must not default to observation_loglik_mc (ADR 0105)"
    )
    assert (
        "log_p_sales_waste_given_ages" in body
        or "sequential_wor" in body
        or "sequential_wor_pmf" in body
    ), "production weights must use exact sequential WOR"


def test_adr_0049_fil04_c_and_0057_historical_after_0091() -> None:
    """T-021 / ADR 0091: FIL-04 → C; FIL-12 historical (no longer ACCEPTED-only)."""
    root = Path(__file__).resolve().parents[1] / ".team" / "adr"
    text_0049 = (root / "0049-fil-04-factorisation-of-age-across-cohorts.md").read_text(
        encoding="utf-8"
    )
    status_0049 = [
        ln.strip() for ln in text_0049.splitlines() if ln.startswith("STATUS:")
    ]
    assert status_0049, "missing STATUS in 0049"
    assert "SUPERSEDED BY 0091" in status_0049[0]
    assert "C" in text_0049 and "mean-field" in text_0049.lower()

    text_0057 = (
        root / "0057-fil-12-making-the-joint-age-posterior-tractable.md"
    ).read_text(encoding="utf-8")
    status_0057 = [
        ln.strip() for ln in text_0057.splitlines() if ln.startswith("STATUS:")
    ]
    assert status_0057, "missing STATUS in 0057"
    assert "HISTORICAL" in status_0057[0]


def test_metrics_helpers_and_stockout_path() -> None:
    """Exercise metric helpers + stockout / zero-sales / MF induced joint."""
    from blueberries_voi.filter import age_likelihood as al

    params = ModelParams()
    n = [2, 2]
    tau_grid = [1.0, 4.0]
    prior_j = np.ones(4, dtype=float) / 4.0
    prior_m = np.ones((2, 2), dtype=float) / 2.0
    y_stockout = P1Obs(sales_total=4, waste_total=0, arrivals=0)
    y_zero = P1Obs(sales_total=0, waste_total=0, arrivals=0)

    post_j = al.exact_joint_update(n, prior_j, y_stockout, params, tau_grid=tau_grid)
    post_m = al.mean_field_update(n, prior_m, y_stockout, params, tau_grid=tau_grid)
    induced = al.induced_joint_from_marginals(post_m)
    assert post_j.shape == (4,)
    assert abs(float(post_j.sum()) - 1.0) < 1e-9
    assert abs(float(induced.sum()) - 1.0) < 1e-9

    tv = al.joint_total_variation(post_j, induced)
    assert 0.0 <= tv <= 1.0
    kl = al.joint_kl(post_j, induced)
    assert kl >= 0.0
    marg = al.marginals_from_joint(post_j, L=2, K=2)
    assert marg.shape == (2, 2)
    assert al.marginal_kl(marg[0], post_m[0]) >= 0.0
    assert al.marginal_total_variation(marg[0], post_m[0]) >= 0.0
    mi = al.max_pairwise_mutual_information(post_j, L=2, K=2)
    assert mi >= 0.0
    assert al.max_pairwise_mutual_information(post_j, L=1, K=2) == 0.0

    sw_j = al.survival_weighted_on_hand(
        n, post_j, params=params, tau_grid=tau_grid, from_marginals=False
    )
    sw_m = al.survival_weighted_on_hand(
        n, post_m, params=params, tau_grid=tau_grid, from_marginals=True
    )
    assert sw_j > 0.0 and sw_m > 0.0

    w = np.array([0.5, 0.5], dtype=float)
    assert al.sequential_wor_composition_prob(n, [0, 0], w) == 1.0
    table = al.sequential_wor_composition_probs(n, 2, w)
    assert sum(table.values()) > 0.99
    ll0 = al.log_p_sales_waste_given_ages(n, tau_grid, 0, 0, params)
    assert math.isfinite(ll0)
    post0 = al.exact_joint_update(n, prior_j, y_zero, params, tau_grid=tau_grid)
    assert abs(float(post0.sum()) - 1.0) < 1e-9

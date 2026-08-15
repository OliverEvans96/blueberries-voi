"""T-069 / ADR 0106: ShelfBelief age rows are arrival-prior exports (RED).

Locks arrival-derived ``age_marginals`` (not MF posteriors), ENG-01 flatten
``L·K`` wire shape, Stage A honesty (F2a/F2 via priors; P0/P1/F1 not in-store
age-learning gates), and the plain-English changelog rationale for dropping RB age.
"""

from __future__ import annotations

import pytest

pytest.skip(
    "T-121 F3: ADR 0127 Wave F supersession — shelf_belief_from_rbpf removed",
    allow_module_level=True,
)

import ast
import inspect
import re
from pathlib import Path
from typing import Any
from typing import Any as RBPF  # T-121 F3, shelf_belief_from_rbpf

import numpy as np

from blueberries_voi.filter.age_likelihood import mean_field_update
from blueberries_voi.filter.arrival_priors import (
    arrival_age_prior_f2,
    delivery_birth_age_prior,
)
from blueberries_voi.filter.types import UNOBSERVED, RichObs, age_grid, mask_for
from blueberries_voi.model import ModelParams
from blueberries_voi.simulator.belief import flatten_shelf_belief

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CHANGELOG = _REPO_ROOT / ".team" / "changelog.md"
_BELIEF_PY = _REPO_ROOT / "src" / "blueberries_voi" / "filter" / "belief.py"
_STAGE_A_DOC_PATHS = (
    _REPO_ROOT / "experiments" / "fil11_stage_a_result.md",
    _REPO_ROOT / "experiments" / "fil11_stage_a_scenarios.md",
    _REPO_ROOT / "experiments" / "fil11_a.py",
    _REPO_ROOT / "experiments" / "fil11_a_scenarios.py",
    _REPO_ROOT / "src" / "blueberries_voi" / "viz" / "fil11.py",
)

_F2_NEAREST_BIN_MASS_MIN = 0.95
_FLAT_BELIEF_KEYS = frozenset({"lot_counts", "age_marginals", "tau_grid", "L", "K"})


def _as_nested(value: Any) -> list[list[float]]:
    arr = np.asarray(value, dtype=float)
    assert arr.ndim == 2, f"age_marginals must be nested (L, K); got {arr.shape}"
    return [[float(x) for x in row] for row in arr]


def _lot_tv(a: np.ndarray, b: np.ndarray) -> float:
    return 0.5 * float(
        np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)).sum()
    )


def _f2_delivery_rbpf(
    *,
    K: int = 6,
    L: int = 2,
    N: int = 32,
    seed: int = 7,
    sales_total: int = 10,
    waste_total: int = 1,
) -> tuple[RBPF, np.ndarray, float]:
    """RBPF after an F2 delivery that injects a Dirac birth prior on the newest lot."""
    params = ModelParams()
    grid = age_grid(K)
    tau = float(grid[2])
    full = RichObs(
        arrivals=8,
        sales_total=sales_total,
        waste_total=waste_total,
        sales_by_lot={},
        waste_by_lot={},
        pack_date=UNOBSERVED,
        age_at_receipt=tau,
        lot_ids_live=frozenset(),
    )
    obs = mask_for("F2").apply(full)
    assert obs.age_at_receipt == tau
    rbpf = RBPF(params=params, N=N, K=K, L=L)
    rng = np.random.default_rng(seed)
    rbpf.initialize(rng)
    rbpf.step(obs, rng)
    birth = arrival_age_prior_f2(tau, grid=grid)
    return rbpf, birth, tau


def _stage_a_doc_text() -> str:
    chunks: list[str] = []
    for path in _STAGE_A_DOC_PATHS:
        assert path.is_file(), f"missing Stage A doc/harness path: {path}"
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _changelog_t069_entry() -> str | None:
    text = _CHANGELOG.read_text(encoding="utf-8")
    # Prefer a heading/bullet that cites T-069; fall back to scanning whole file.
    parts = re.split(r"\n(?=## )", text)
    for part in parts:
        if re.search(r"\bT-069\b", part, flags=re.IGNORECASE):
            return part
    if re.search(r"\bT-069\b", text, flags=re.IGNORECASE):
        return text
    return None


# ---------------------------------------------------------------------------
# AC: shelf_belief_from_rbpf exports arrival-derived age_marginals (not MF)
# ---------------------------------------------------------------------------


def test_shelf_belief_from_rbpf_docs_state_arrival_prior_not_mf() -> None:
    """ADR 0106: factory/module docs must describe arrival-prior age rows, not MF."""
    src = _BELIEF_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    factory = None
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "shelf_belief_from_rbpf"
        ):
            factory = node
            break
    assert factory is not None, "shelf_belief_from_rbpf must exist in filter/belief.py"
    factory_doc = ast.get_docstring(factory) or ""
    module_doc = ast.get_docstring(tree) or ""
    joined = f"{module_doc}\n{factory_doc}\n{src[:800]}".lower()

    assert "0106" in src or "arrival" in factory_doc.lower(), (
        "shelf_belief_from_rbpf docs must cite ADR 0106 or arrival-prior age exports"
    )
    assert any(
        tok in joined
        for tok in (
            "arrival prior",
            "arrival-prior",
            "arrival-derived",
            "birth prior",
            "arrival belief",
        )
    ), (
        "belief export docs must state age_marginals are arrival-prior / birth-prior "
        "exports (ADR 0106)"
    )
    assert (
        "mf " not in factory_doc.lower() and "mean-field" not in factory_doc.lower()
    ), (
        "shelf_belief_from_rbpf docstring must not claim MF / mean-field posteriors "
        "(superseded by ADR 0106)"
    )
    assert "mean field" not in factory_doc.lower()
    # Module blurb still saying "MF marginals" as the production ShelfBelief story
    # is also banned once 0106 lands.
    assert "mf marginal" not in module_doc.lower(), (
        "belief.py module docstring must not describe ShelfBelief as MF marginals"
    )


def test_shelf_belief_from_rbpf_f2_dirac_matches_birth_prior_shape() -> None:
    """AC: F2 Dirac birth path → newest-lot age_marginals match arrival prior; (L,K)."""
    rbpf, birth, _tau = _f2_delivery_rbpf()
    belief = shelf_belief_from_rbpf(rbpf)
    margs = _as_nested(belief.age_marginals)
    L, K = int(rbpf.L), int(rbpf.K)
    assert len(margs) == L
    assert all(len(row) == K for row in margs)
    newest = np.asarray(margs[-1], dtype=float)
    assert newest.shape == (K,)
    assert abs(float(newest.sum()) - 1.0) < 1e-6
    np.testing.assert_allclose(newest, birth, atol=1e-9, rtol=0.0)
    nearest = int(np.argmax(birth))
    assert float(newest[nearest]) >= _F2_NEAREST_BIN_MASS_MIN


def test_shelf_belief_from_rbpf_ages_differ_from_mean_field_update() -> None:
    """AC: exported ages are not sales-updated MF posteriors (diagn
    ostic MF ≠ export)."""
    rbpf, birth, _tau = _f2_delivery_rbpf(sales_total=12, waste_total=2)
    belief = shelf_belief_from_rbpf(rbpf)
    margs = _as_nested(belief.age_marginals)
    newest = np.asarray(margs[-1], dtype=float)

    # Diagnostic MF on the same birth prior + storewide totals would rewrite ages.
    from blueberries_voi.filter.types import P1Obs

    counts = [max(round(c), 1) for c in belief.lot_counts]
    prior_rows = np.asarray(margs, dtype=float)
    # Use the birth prior on every row so MF has a clean sales-update contrast.
    prior_rows = np.broadcast_to(birth, prior_rows.shape).copy()
    y = P1Obs(sales_total=12, waste_total=2, arrivals=8)
    mf = np.asarray(
        mean_field_update(
            counts,
            prior_rows,
            y,
            rbpf.params,
            tau_grid=list(belief.tau_grid),
        ),
        dtype=float,
    )
    assert mf.shape == prior_rows.shape
    # MF should move at least one row vs the Dirac birth prior under non-trivial sales.
    moved = any(_lot_tv(mf[ell], birth) > 1e-6 for ell in range(mf.shape[0]))
    assert moved, "fixture must make mean_field_update move ages vs birth prior"

    # Export must stay on the arrival/birth row for the newest lot, not MF.
    assert _lot_tv(newest, birth) <= 1e-9, (
        "newest-lot age_marginals must match F2 arrival Dirac, not MF rewrite"
    )
    assert _lot_tv(newest, mf[-1]) > 1e-6, (
        "exported age_marginals must differ from mean_field_update posteriors"
    )


def test_shelf_belief_from_rbpf_f2a_path_matches_delivery_birth_prior() -> None:
    """AC: F2a pack-date birth path → newest-lot export matches del
    ivery_birth_age_prior."""
    from datetime import date, timedelta

    params = ModelParams()
    K, L, N = 8, 3, 40
    grid = age_grid(K)
    as_of = date(2024, 3, 10)
    pack = as_of - timedelta(days=4)
    full = RichObs(
        arrivals=8,
        sales_total=10,
        waste_total=1,
        sales_by_lot=UNOBSERVED,
        waste_by_lot=UNOBSERVED,
        pack_date=pack,
        age_at_receipt=UNOBSERVED,
        lot_ids_live=UNOBSERVED,
    )
    obs = mask_for("F2a").apply(full)
    assert obs.pack_date == pack
    rbpf = RBPF(params=params, N=N, K=K, L=L)
    rng = np.random.default_rng(11)
    rbpf.initialize(rng)
    rbpf.step(obs, rng)
    expected = np.asarray(delivery_birth_age_prior(obs, grid, params), dtype=float)

    belief = shelf_belief_from_rbpf(rbpf)
    margs = _as_nested(belief.age_marginals)
    assert len(margs) == L
    assert all(len(row) == K for row in margs)
    newest = np.asarray(margs[-1], dtype=float)
    np.testing.assert_allclose(newest, expected, atol=1e-9, rtol=0.0)


# ---------------------------------------------------------------------------
# AC: ENG-01 flatten remains wire-compatible (flat length L*K)
# ---------------------------------------------------------------------------


def test_flatten_shelf_belief_from_rbpf_is_wire_compatible_l_times_k() -> None:
    """AC: flatten_shelf_belief keeps ENG-01 field names and flat age length L·K."""
    rbpf, _birth, _tau = _f2_delivery_rbpf()
    belief = shelf_belief_from_rbpf(rbpf)
    flat = flatten_shelf_belief(belief)

    assert set(flat) >= _FLAT_BELIEF_KEYS
    l_dim = int(flat["L"])
    k_dim = int(flat["K"])
    assert l_dim == int(rbpf.L)
    assert k_dim == int(rbpf.K)
    assert len(list(flat["lot_counts"])) == l_dim
    age_flat = list(flat["age_marginals"])
    assert len(age_flat) == l_dim * k_dim
    assert all(isinstance(x, float) for x in age_flat)
    # Nested rows must not appear on the wire.
    for i, x in enumerate(age_flat):
        assert not isinstance(x, (list, tuple)), (
            f"age_marginals[{i}] nested; ENG-01 wire requires flat L*K"
        )
    assert len(list(flat["tau_grid"])) == k_dim


def test_flatten_shelf_belief_row_major_matches_nested_arrival_rows() -> None:
    """Flat buffer is row-major concatenation of nested (L, K) arrival age rows."""
    rbpf, birth, _tau = _f2_delivery_rbpf()
    belief = shelf_belief_from_rbpf(rbpf)
    nested = _as_nested(belief.age_marginals)
    flat = flatten_shelf_belief(belief)
    expected = [float(x) for row in nested for x in row]
    assert list(flat["age_marginals"]) == expected
    # Newest lot slice still carries the F2 Dirac birth prior.
    k_dim = int(flat["K"])
    newest_flat = list(flat["age_marginals"])[-k_dim:]
    np.testing.assert_allclose(newest_flat, birth, atol=1e-9, rtol=0.0)


# ---------------------------------------------------------------------------
# AC: Stage A docs/harness honesty - F2a/F2 via priors; P0/P1/F1 not in-store gates
# ---------------------------------------------------------------------------


def test_stage_a_docs_state_f2_age_information_comes_from_priors() -> None:
    """AC: Stage A-style docs/harness state F2a/F2 age info comes from priors."""
    text = _stage_a_doc_text().lower()
    assert "f2a" in text and "f2" in text
    prior_tokens = (
        "arrival prior",
        "arrival-prior",
        "from priors",
        "birth prior",
        "via priors",
        "age information comes from",
        "ages come from prior",
        "prior injection",
    )
    assert any(tok in text for tok in prior_tokens), (
        "experiments/ Stage A docs and fil11 harness must state that F2a/F2 age "
        "information comes from priors (ADR 0105/0106 / T-069)"
    )


def test_stage_a_docs_p0_p1_f1_do_not_claim_instore_age_learning_gate() -> None:
    """AC: P0/P1/F1 must not claim in-store age learning/contractio
    n as a production gate."""
    text = _stage_a_doc_text().lower()
    for rung in ("p0", "p1", "f1"):
        assert rung in text, f"Stage A docs must mention {rung.upper()}"

    honesty_tokens = (
        "not a production gate",
        "not claim in-store",
        "do not claim in-store",
        "no in-store age learning",
        "in-store age learning was dropped",
        "not gated on in-store",
        "not a gate on in-store",
        "count calibration",
        "arrival-prior injection",
        "arrival prior injection",
    )
    assert any(tok in text for tok in honesty_tokens), (
        "Stage A docs/harness must state that P0/P1/F1 do not claim in-store age "
        "learning / contraction as a production gate (T-069)"
    )
    # Ban leftover framing that treats P1 sales contraction as the settle.
    banned = (
        "p0/p1/f1 in-store age learning is the production gate",
        "production gate is age posterior contraction under p1",
        "gate on in-store age learning for p0",
    )
    for phrase in banned:
        assert phrase not in text, (
            f"Stage A docs still claim banned gate framing: {phrase}"
        )


# ---------------------------------------------------------------------------
# AC: changelog plain-English - RB age removed because in-store learning dropped
# ---------------------------------------------------------------------------


def test_changelog_states_rb_age_removed_because_instore_learning_dropped() -> None:
    """AC: changelog cites T-069 and the locked rationale (not 'boo
    tstrap is simpler')."""
    assert _CHANGELOG.is_file(), f"missing {_CHANGELOG}"
    entry = _changelog_t069_entry()
    assert entry is not None, (
        ".team/changelog.md must include a plain-English T-069 entry explaining "
        "that Rao-Blackwellised / in-store age marginalisation was removed because "
        "in-store age learning was dropped"
    )
    lowered = entry.lower()
    assert "t-069" in lowered
    assert any(
        tok in lowered
        for tok in (
            "rao-blackwell",
            "rao-blackwell",
            "rao blackwell",
            "rb age",
            "age marginalisation",
            "age marginalization",
            "in-store age",
        )
    ), "T-069 changelog must mention RB / in-store age marginalisation removal"
    assert "in-store" in lowered and "age" in lowered
    assert any(
        tok in lowered
        for tok in (
            "learning was dropped",
            "learning dropped",
            "dropped in-store",
            "stop learning ages",
            "no longer learn",
            "do not learn ages",
            "in-store age learning was dropped",
        )
    ), (
        "T-069 changelog must say in-store age learning was dropped "
        "(ADR 0105 locked rationale)"
    )
    # Reject the discarded "bootstrap is simpler" rationale as the stated reason.
    if "bootstrap" in lowered and "simpler" in lowered:
        assert any(
            tok in lowered
            for tok in (
                "not because",
                "not that",
                "not simply",
                "not merely",
                "rather than",
            )
        ), (
            "If changelog mentions bootstrap/simpler, reject that as the reason "
            "(ADR 0105 alternative)"
        )


def test_shelf_belief_from_rbpf_still_exported_for_ctl_path() -> None:
    """Sanity: factory remains the CTL/ENG-01 entry point (shape co
    ntract lives here)."""
    assert callable(shelf_belief_from_rbpf)
    sig = inspect.signature(shelf_belief_from_rbpf)
    assert len(sig.parameters) >= 1

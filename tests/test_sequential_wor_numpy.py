"""T-065 NumPy sequential-WOR composition DP — retired with τ filter."""

from __future__ import annotations

import pytest

pytest.skip(
    "T-TAU-RETIRE: filter.age_likelihood module deleted",
    allow_module_level=True,
)

import ast
import inspect
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest

from blueberries_voi.filter import age_likelihood as al
from blueberries_voi.model import allocate_sales

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

_ATOL = 0.0
_RTOL = 0.0


def _sequential_wor_composition_probs_ref(
    counts: Sequence[int],
    sales_tot: int,
    weights: NDArray[np.floating],
) -> dict[tuple[int, ...], float]:
    """Frozen pure-Python DP (pre-T-065 loop) for numeric identity."""
    counts_l = [int(c) for c in counts]
    n_lots = len(counts_l)
    if n_lots == 0:
        return {(): 1.0} if sales_tot == 0 else {}
    if sales_tot < 0 or sales_tot > int(sum(counts_l)):
        return {}
    if sales_tot == 0:
        return {tuple(0 for _ in range(n_lots)): 1.0}

    dims = [c + 1 for c in counts_l]
    size = 1
    for d in dims:
        size *= d
    strides = [1] * n_lots
    for i in range(n_lots - 2, -1, -1):
        strides[i] = strides[i + 1] * dims[i + 1]

    def pack(c: Sequence[int]) -> int:
        return sum(int(c[i]) * strides[i] for i in range(n_lots))

    def unpack(idx: int) -> tuple[int, ...]:
        out: list[int] = []
        rem = idx
        for i in range(n_lots):
            out.append(rem // strides[i])
            rem %= strides[i]
        return tuple(out)

    cur = np.zeros(size, dtype=float)
    cur[pack([0] * n_lots)] = 1.0
    w = np.asarray(weights, dtype=float)

    for _ in range(sales_tot):
        nxt = np.zeros(size, dtype=float)
        for idx, p in enumerate(cur):
            if p <= 0.0:
                continue
            c = unpack(idx)
            avail = [float(w[j]) if c[j] < counts_l[j] else 0.0 for j in range(n_lots)]
            tot = float(sum(avail))
            if tot <= 0.0:
                continue
            for j in range(n_lots):
                if avail[j] <= 0.0:
                    continue
                c2 = list(c)
                c2[j] += 1
                nxt[pack(c2)] += p * (avail[j] / tot)
        cur = nxt

    out: dict[tuple[int, ...], float] = {}
    for idx, p in enumerate(cur):
        if p > 0.0:
            out[unpack(idx)] = float(p)
    return out


def _assert_tables_equal(
    got: dict[tuple[int, ...], float],
    ref: dict[tuple[int, ...], float],
) -> None:
    assert set(got) == set(ref), f"key mismatch got={set(got)} ref={set(ref)}"
    for key in ref:
        np.testing.assert_allclose(got[key], ref[key], rtol=_RTOL, atol=_ATOL)


def test_public_signature_unchanged() -> None:
    sig = inspect.signature(al.sequential_wor_composition_probs)
    params = list(sig.parameters)
    assert params == ["counts", "sales_tot", "weights"]
    table = al.sequential_wor_composition_probs([2, 2], 1, np.asarray([1.0, 1.0]))
    assert isinstance(table, dict)
    assert all(isinstance(k, tuple) for k in table)
    assert all(isinstance(v, float) for v in table.values())


@pytest.mark.parametrize(
    ("counts", "sales_tot", "weights"),
    [
        ([2, 2], 0, np.asarray([1.0, 2.0])),
        ([2, 2], 1, np.asarray([1.0, 2.0])),
        ([2, 2], 2, np.asarray([1.0, 2.0])),
        ([3, 2], 3, np.asarray([0.5, 1.5])),
        ([2, 2, 2], 2, np.asarray([1.0, 1.0, 1.0])),
        ([3, 1, 2], 3, np.asarray([2.0, 1.0, 0.5])),
        ([1, 1, 1], 2, np.asarray([1.0, 3.0, 2.0])),
    ],
)
def test_numpy_dp_matches_frozen_python_ref(
    counts: list[int],
    sales_tot: int,
    weights: NDArray[np.floating],
) -> None:
    ref = _sequential_wor_composition_probs_ref(counts, sales_tot, weights)
    got = al.sequential_wor_composition_probs(counts, sales_tot, weights)
    _assert_tables_equal(got, ref)


def test_boundary_cases_match_ref() -> None:
    w = np.asarray([1.0, 1.0])
    cases: list[tuple[list[int], int]] = [
        ([], 0),
        ([], 1),
        ([2, 2], -1),
        ([2, 2], 5),
        ([0, 0], 0),
        ([3, 3], 6),  # full stockout demand
    ]
    for counts, sales_tot in cases:
        w_use = w[: len(counts)] if counts else w[:0]
        ref = _sequential_wor_composition_probs_ref(counts, sales_tot, w_use)
        got = al.sequential_wor_composition_probs(counts, sales_tot, w_use)
        _assert_tables_equal(got, ref)


def test_fixed_weights_not_remaining_times_weights() -> None:
    """Among nonempty cohorts, picks use fixed weights (allocate_sales law)."""
    counts = [2, 2]
    weights = np.asarray([1.0, 3.0])
    table = al.sequential_wor_composition_probs(counts, 1, weights)
    # First pick: P(lot0)=1/4, P(lot1)=3/4.
    assert table[(1, 0)] == pytest.approx(0.25, abs=1e-15)
    assert table[(0, 1)] == pytest.approx(0.75, abs=1e-15)

    table2 = al.sequential_wor_composition_probs(counts, 2, weights)
    p_02 = 0.75 * 0.75
    p_11 = 0.25 * 0.75 + 0.75 * 0.25
    p_20 = 0.25 * 0.25
    assert table2[(0, 2)] == pytest.approx(p_02, abs=1e-15)
    assert table2[(1, 1)] == pytest.approx(p_11, abs=1e-15)
    assert table2[(2, 0)] == pytest.approx(p_20, abs=1e-15)


def test_composition_probs_align_with_allocate_sales_monte_carlo() -> None:
    """Tiny shelf: DP table close to empirical allocate_sales frequencies."""
    counts_list = [2, 2]
    w = np.asarray([1.0, 3.0], dtype=float)
    sales_tot = 2
    table = al.sequential_wor_composition_probs(counts_list, sales_tot, w)

    rng = np.random.default_rng(0)
    n_mc = 20_000
    freq: dict[tuple[int, ...], int] = {}
    for _ in range(n_mc):
        sold = allocate_sales(counts_list, sales_tot, w, rng)
        key = tuple(int(x) for x in sold)
        freq[key] = freq.get(key, 0) + 1
    for key, p in table.items():
        emp = freq.get(key, 0) / n_mc
        assert abs(emp - p) < 0.02, f"{key}: emp={emp} dp={p}"


def _function_source(name: str) -> str:
    src = Path(al.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    msg = f"{name} not found"
    raise AssertionError(msg)


def test_implementation_is_numpy_vectorized_not_python_unpack_loop() -> None:
    """Structural gate: production DP must not use nested unpack/enumerate loops."""
    body = _function_source("sequential_wor_composition_probs")
    # Pre-rewrite: nested unpack/pack + enumerate(cur).
    assert "def unpack" not in body, (
        "sequential_wor_composition_probs still defines nested unpack — "
        "NumPy rewrite required (T-065)"
    )
    assert "for idx, p in enumerate(cur)" not in body, (
        "sequential_wor_composition_probs still uses Python enumerate over state — "
        "NumPy rewrite required (T-065)"
    )
    # Vectorized rewrite should index with boolean masks / flatnonzero.
    assert (
        "flatnonzero" in body
        or "np.nonzero" in body
        or "astype(bool)" in body
        or "cur > 0" in body
        or "np.where" in body
    ), "expected NumPy vectorized active-state indexing in composition DP"


def test_no_new_runtime_deps() -> None:
    import tomllib

    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    names = {
        d.split(">=")[0].split("==")[0].split("[")[0].strip().lower() for d in deps
    }
    assert "numba" not in names
    assert "cython" not in names

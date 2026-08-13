"""T-064 Unique-particle MF dedup in ``_rbpf_update`` — RED acceptance tests."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.filter import RBPF
from blueberries_voi.filter.age_likelihood import mean_field_update
from blueberries_voi.filter.types import UNOBSERVED, P1Obs, RichObs, mask_for
from blueberries_voi.model import ModelParams

_SIMPLEX_TOL = 1e-6
_RUNTIME_DEPS_LOCKED = frozenset({"matplotlib", "numpy", "pyarrow", "scipy"})


def _backends_source() -> str:
    import blueberries_voi.filter.backends as backends

    return Path(backends.__file__).read_text(encoding="utf-8")


def _ast_function(source: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return node
    msg = f"function {name!r} not found in source"
    raise AssertionError(msg)


def _names_in_function(fn: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


def _p1_unobserved_maps(
    *,
    sales_total: int = 4,
    waste_total: int = 1,
    arrivals: int = 0,
) -> RichObs:
    return mask_for("P1").apply(
        RichObs(
            arrivals=arrivals,
            sales_total=sales_total,
            waste_total=waste_total,
            sales_by_lot={1: sales_total, 2: 0},
            waste_by_lot={1: waste_total, 2: 0},
            pack_date=UNOBSERVED,
            age_at_receipt=UNOBSERVED,
            lot_ids_live=UNOBSERVED,
        )
    )


def _f1_lot_maps(*, sales_by_lot: dict[int, int]) -> RichObs:
    total = int(sum(sales_by_lot.values()))
    return mask_for("F1").apply(
        RichObs(
            arrivals=0,
            sales_total=total,
            waste_total=0,
            sales_by_lot=sales_by_lot,
            waste_by_lot=UNOBSERVED,
            pack_date=UNOBSERVED,
            age_at_receipt=UNOBSERVED,
            lot_ids_live=frozenset(sales_by_lot),
        )
    )


def _fingerprint(counts_i: np.ndarray, age_post_i: np.ndarray) -> tuple[Any, bytes]:
    return (tuple(counts_i.tolist()), age_post_i.tobytes())


def test_adr_0097_accepted() -> None:
    adr = Path(__file__).resolve().parents[1] / ".team/adr/0097-exact-faster-p1-f2a-likelihood.md"
    text = adr.read_text(encoding="utf-8")
    assert "STATUS: ACCEPTED" in text
    assert "2026-08-12" in text


def test_no_new_runtime_deps() -> None:
    import tomllib

    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    names = {d.split(">=")[0].split("==")[0].split("[")[0].strip().lower() for d in deps}
    assert names <= _RUNTIME_DEPS_LOCKED


def test_duplicate_particles_invoke_mf_once_per_unique_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N≥4 with duplicates → mean_field_update call count == unique keys."""
    import blueberries_voi.filter.age_likelihood as age_likelihood
    import blueberries_voi.filter.backends as backends

    calls: list[int] = []
    real = age_likelihood.mean_field_update

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(age_likelihood, "mean_field_update", _spy)
    if hasattr(backends, "mean_field_update"):
        monkeypatch.setattr(backends, "mean_field_update", _spy)

    n, k, l = 6, 4, 2
    rbpf = RBPF(params=ModelParams(), N=n, K=k, L=l)
    rng = np.random.default_rng(42)
    rbpf.initialize(rng)
    assert rbpf._state is not None

    # Two shared keys: particles 0,1,2 share A; 3,4 share B; 5 is unique → 3 keys.
    counts_a = np.asarray([5, 5], dtype=int)
    counts_b = np.asarray([4, 6], dtype=int)
    counts_c = np.asarray([3, 7], dtype=int)
    post_a = np.ones((l, k), dtype=float) / k
    post_b = np.asarray([[0.7, 0.1, 0.1, 0.1], [0.1, 0.7, 0.1, 0.1]], dtype=float)
    post_c = np.asarray([[0.25, 0.25, 0.25, 0.25], [0.4, 0.2, 0.2, 0.2]], dtype=float)

    rbpf._state.counts[:] = np.vstack(
        [counts_a, counts_a, counts_a, counts_b, counts_b, counts_c]
    )
    rbpf._state.age_post[:] = np.stack(
        [post_a, post_a, post_a, post_b, post_b, post_c], axis=0
    )

    keys = [
        _fingerprint(rbpf._state.counts[i], rbpf._state.age_post[i]) for i in range(n)
    ]
    n_unique = len(set(keys))
    assert n_unique == 3
    assert n_unique < n

    obs = _p1_unobserved_maps(sales_total=4, waste_total=1, arrivals=0)
    rbpf.step(obs, rng)

    assert len(calls) == n_unique, (
        f"expected mean_field_update call count == {n_unique} unique keys, "
        f"got {len(calls)} (N={n}); unique-particle MF dedup missing"
    )


def test_duplicate_particles_match_naive_per_particle_mf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deduped posteriors must equal naive per-particle mean_field_update."""
    import blueberries_voi.filter.backends as backends
    from blueberries_voi.filter.types import age_grid
    from blueberries_voi.model import q10_age_increment

    n, k, l = 4, 4, 2
    params = ModelParams()
    rbpf = RBPF(params=params, N=n, K=k, L=l)
    rng = np.random.default_rng(7)
    rbpf.initialize(rng)
    assert rbpf._state is not None

    counts_a = np.asarray([5, 5], dtype=int)
    counts_b = np.asarray([4, 6], dtype=int)
    post_a = np.ones((l, k), dtype=float) / k
    post_b = np.asarray([[0.6, 0.2, 0.1, 0.1], [0.2, 0.6, 0.1, 0.1]], dtype=float)
    rbpf._state.counts[:] = np.vstack([counts_a, counts_a, counts_b, counts_b])
    rbpf._state.age_post[:] = np.stack([post_a, post_a, post_b, post_b], axis=0)

    counts0 = rbpf._state.counts.copy()
    post0 = rbpf._state.age_post.copy()
    days0 = rbpf._state.days_on_shelf.copy()

    sales_tot, waste_tot = 4, 1
    y_p1 = P1Obs(sales_total=sales_tot, waste_total=waste_tot, arrivals=0)
    grid = age_grid(k)
    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    days = days0.astype(float) + 1.0
    tau_grid = grid + float(np.mean(days)) * float(dtau)
    naive = np.empty_like(post0)
    for i in range(n):
        naive[i] = mean_field_update(
            counts0[i],
            post0[i],
            y_p1,
            params,
            tau_grid=tau_grid,
            max_sweeps=2,
        )

    # Keep particle order so index-wise identity vs naive is meaningful.
    monkeypatch.setattr(backends, "_ess", lambda _w: float(n))

    obs = _p1_unobserved_maps(sales_total=sales_tot, waste_total=waste_tot, arrivals=0)
    out = backends._rbpf_update(
        rbpf._state,
        obs,
        params,
        np.random.default_rng(0),
        backend_name="mean_field",
    )

    for i in range(n):
        np.testing.assert_array_equal(
            out.age_post[i],
            naive[i],
            err_msg=f"particle {i} age_post differs from naive MF reference",
        )
    np.testing.assert_array_equal(out.age_post[0], out.age_post[1])
    np.testing.assert_array_equal(out.age_post[2], out.age_post[3])


def test_all_distinct_fingerprints_call_once_per_particle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.filter.age_likelihood as age_likelihood
    import blueberries_voi.filter.backends as backends

    calls: list[int] = []
    real = age_likelihood.mean_field_update

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(age_likelihood, "mean_field_update", _spy)
    if hasattr(backends, "mean_field_update"):
        monkeypatch.setattr(backends, "mean_field_update", _spy)

    n, k, l = 4, 4, 2
    rbpf = RBPF(params=ModelParams(), N=n, K=k, L=l)
    rng = np.random.default_rng(99)
    rbpf.initialize(rng)
    assert rbpf._state is not None

    for i in range(n):
        rbpf._state.counts[i] = np.asarray([3 + i, 5], dtype=int)
        post = np.ones((l, k), dtype=float) / k
        post[0, i % k] += 0.2
        post[0] /= post[0].sum()
        rbpf._state.age_post[i] = post

    keys = [
        _fingerprint(rbpf._state.counts[i], rbpf._state.age_post[i]) for i in range(n)
    ]
    assert len(set(keys)) == n

    rbpf.step(_p1_unobserved_maps(sales_total=3, waste_total=1), rng)
    assert len(calls) == n


def test_lot_map_path_skips_mf_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    import blueberries_voi.filter.age_likelihood as age_likelihood
    import blueberries_voi.filter.backends as backends

    mf_calls: list[int] = []
    lot_calls: list[int] = []
    real_mf = age_likelihood.mean_field_update
    real_lot = backends._apply_lot_map_age_update

    def _spy_mf(*args: Any, **kwargs: Any) -> Any:
        mf_calls.append(1)
        return real_mf(*args, **kwargs)

    def _spy_lot(*args: Any, **kwargs: Any) -> Any:
        lot_calls.append(1)
        return real_lot(*args, **kwargs)

    monkeypatch.setattr(age_likelihood, "mean_field_update", _spy_mf)
    if hasattr(backends, "mean_field_update"):
        monkeypatch.setattr(backends, "mean_field_update", _spy_mf)
    monkeypatch.setattr(backends, "_apply_lot_map_age_update", _spy_lot)

    rbpf = RBPF(params=ModelParams(), N=4, K=4, L=2)
    rng = np.random.default_rng(3)
    rbpf.initialize(rng)
    assert rbpf._state is not None
    rbpf._state.counts[:] = np.asarray([[8, 8]] * 4, dtype=int)
    rbpf.step(_f1_lot_maps(sales_by_lot={1: 10, 2: 2}), rng)
    assert lot_calls, "_apply_lot_map_age_update must run on F1 lot maps"
    assert not mf_calls, "mean_field_update must not run on lot-map path"


def test_rbpf_update_still_names_mean_field_update() -> None:
    fn = _ast_function(_backends_source(), "_rbpf_update")
    assert "mean_field_update" in _names_in_function(fn)

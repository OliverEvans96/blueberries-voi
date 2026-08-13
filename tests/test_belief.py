"""T-023 Belief API (`ShelfBelief`) — RED acceptance contracts.

Locks ADR 0092 / `.team/specs/T-023.md` public surface under `filter/belief.py`
before production code exists. No CTL-01 policy math beyond `effective_inventory`.
"""

from __future__ import annotations

import importlib
import inspect
import json
from dataclasses import FrozenInstanceError, fields, is_dataclass
from typing import Any

import numpy as np
import pytest

from blueberries_voi.filter import PRODUCTION_BACKEND, RBPF, P1Obs
from blueberries_voi.filter.age_likelihood import survival_weighted_on_hand
from blueberries_voi.filter.types import age_grid
from blueberries_voi.model import ModelParams, weibull_survival

# Provisional pending-order convention (T-023 open question; freeze with T-024):
# mapping days-until-arrival → order quantity (units).
PendingOrders = dict[int, int]

_BELIEF_MODULES = (
    "blueberries_voi.filter.belief",
    "blueberries_voi.filter",
)

# Public field names preferred by ADR 0092 (list/float-friendly shelf summary).
_REQUIRED_FIELD_NAMES = frozenset({"lot_counts", "age_marginals", "tau_grid"})


def _load_attr(attr: str) -> Any | None:
    for name in _BELIEF_MODULES:
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        found = getattr(mod, attr, None)
        if found is not None:
            return found
    return None


def _resolve(attr: str) -> Any:
    found = _load_attr(attr)
    assert found is not None, (
        f"{attr} must be exported from blueberries_voi.filter.belief "
        f"(and re-exported on blueberries_voi.filter) per T-023 / ADR 0092; "
        f"tried {_BELIEF_MODULES}"
    )
    return found


def _public_field_names(belief: Any) -> set[str]:
    if is_dataclass(belief):
        return {f.name for f in fields(belief)}
    if hasattr(belief, "__dataclass_fields__"):
        return set(belief.__dataclass_fields__)
    return {k for k in vars(belief) if not k.startswith("_")}


def _as_nested_floats(value: Any) -> list[list[float]]:
    arr = np.asarray(value, dtype=float)
    assert arr.ndim == 2, f"age marginals must be (L, K); got shape {arr.shape}"
    return [[float(x) for x in row] for row in arr]


def _as_int_list(value: Any) -> list[int]:
    return [int(x) for x in list(value)]


def _export_payload(belief: Any) -> Any:
    if hasattr(belief, "to_export"):
        return belief.to_export()
    if is_dataclass(belief) and not isinstance(belief, type):
        from dataclasses import asdict

        return asdict(belief)
    msg = "ShelfBelief must expose to_export() or be a dataclass with list/float fields"
    raise AssertionError(msg)


def _round_trip(belief_cls: Any, belief: Any) -> Any:
    payload = _export_payload(belief)
    if hasattr(belief_cls, "from_export"):
        return belief_cls.from_export(payload)
    return belief_cls(**payload)


def _flat_prior_expected_survival(params: ModelParams, tau_grid: list[float]) -> float:
    """E_g[S(τ)] under flat arrival-age prior on the discrete grid (pipeline weight)."""
    if not tau_grid:
        return 0.0
    s = [
        weibull_survival(float(t), beta=params.beta, eta=params.eta_ref)
        for t in tau_grid
    ]
    return float(sum(s) / len(s))


def _stepped_production_rbpf(*, seed: int = 11) -> RBPF:
    # ADR 0105: production identity is counts-only arrival-age, not age mean-field.
    assert PRODUCTION_BACKEND != "mean_field"
    params = ModelParams()
    rbpf = RBPF(params=params, N=40, K=6, L=2)
    rng = np.random.default_rng(seed)
    rbpf.initialize(rng)
    rbpf.step(P1Obs(sales_total=8, waste_total=1, arrivals=0), rng)
    return rbpf


def _weighted_mean_counts(rbpf: RBPF) -> list[float]:
    """Test-only expected counts (weight-averaged particles). Not a CTL path."""
    state = rbpf._state
    assert state is not None
    w = np.asarray(state.weights, dtype=float)
    counts = np.asarray(state.counts, dtype=float)
    mean = (w[:, None] * counts).sum(axis=0) / max(float(w.sum()), 1e-300)
    return [float(x) for x in mean]


# ---------------------------------------------------------------------------
# AC: ShelfBelief importable from blueberries_voi.filter
# ---------------------------------------------------------------------------


def test_shelf_belief_importable_from_filter_package() -> None:
    ShelfBelief = _resolve("ShelfBelief")
    filter_pkg = importlib.import_module("blueberries_voi.filter")
    assert getattr(filter_pkg, "ShelfBelief", None) is ShelfBelief
    assert "ShelfBelief" in getattr(filter_pkg, "__all__", ())


def test_shelf_belief_module_exports_factories_and_effective_inventory() -> None:
    for name in (
        "ShelfBelief",
        "shelf_belief_from_rbpf",
        "shelf_belief_from_oracle",
        "effective_inventory",
    ):
        _resolve(name)


def test_controller_consumers_import_belief_from_filter_not_rbpf_state() -> None:
    """Controller may import ShelfBelief from filter; must not need RBPF._state."""
    ShelfBelief = _resolve("ShelfBelief")
    import blueberries_voi.controller  # noqa: F401 — package exists for CTL imports

    # Usable type object for annotations / fixtures without touching filter internals.
    assert ShelfBelief is not None
    assert not hasattr(ShelfBelief, "_state")


def test_shelf_belief_is_frozen_public_type() -> None:
    ShelfBelief = _resolve("ShelfBelief")
    from_oracle = _resolve("shelf_belief_from_oracle")
    grid = [float(x) for x in age_grid(4)]
    belief = from_oracle(lot_counts=[3], ages=[2.0], tau_grid=grid)
    assert is_dataclass(belief) or is_dataclass(ShelfBelief)
    names = _public_field_names(belief)
    assert names >= _REQUIRED_FIELD_NAMES
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        belief.lot_counts = [99]


# ---------------------------------------------------------------------------
# AC: shelf_belief_from_rbpf → ShelfBelief with (L, K) arrival-prior age rows
# (ADR 0106 supersedes ADR 0092 MF-posterior reading; T-069)
# ---------------------------------------------------------------------------


def test_shelf_belief_from_rbpf_matches_arrival_age_rows_shape_and_values() -> None:
    """Nested (L, K) age_marginals match filter-carried arrival ages (not MF docs)."""
    from_rbpf = _resolve("shelf_belief_from_rbpf")
    rbpf = _stepped_production_rbpf()
    belief = from_rbpf(rbpf)

    assert type(belief).__name__ == "ShelfBelief"
    margs = _as_nested_floats(belief.age_marginals)
    L, K = int(rbpf.L), int(rbpf.K)
    assert len(margs) == L
    assert all(len(row) == K for row in margs)

    for ell in range(L):
        # age_posterior is the filter-carried arrival-age mass (ADR 0105/0106).
        post = np.asarray(rbpf.age_posterior(ell), dtype=float)
        assert post.shape == (K,)
        np.testing.assert_allclose(margs[ell], post, atol=1e-9, rtol=0.0)
        assert abs(sum(margs[ell]) - 1.0) < 1e-6

    # Guard supersession: factory docs must not still claim MF posteriors.
    import blueberries_voi.filter.belief as belief_mod

    factory_doc = (inspect.getdoc(belief_mod.shelf_belief_from_rbpf) or "").lower()
    assert "mf" not in factory_doc and "mean-field" not in factory_doc, (
        "shelf_belief_from_rbpf docstring must not claim MF posteriors (ADR 0106)"
    )
    assert any(tok in factory_doc for tok in ("arrival", "birth prior", "prior")), (
        "shelf_belief_from_rbpf docstring must describe arrival-prior age exports"
    )


def test_shelf_belief_from_rbpf_lot_counts_match_weight_averaged_particles() -> None:
    from_rbpf = _resolve("shelf_belief_from_rbpf")
    rbpf = _stepped_production_rbpf(seed=19)
    belief = from_rbpf(rbpf)
    counts = _as_int_list(belief.lot_counts)
    expected = _weighted_mean_counts(rbpf)
    assert len(counts) == rbpf.L
    # Counts may be rounded ints or float means; allow either public representation.
    got = [float(x) for x in list(belief.lot_counts)]
    np.testing.assert_allclose(got, expected, atol=1e-6, rtol=0.0)


def test_shelf_belief_from_rbpf_requires_initialized_rbpf() -> None:
    from_rbpf = _resolve("shelf_belief_from_rbpf")
    rbpf = RBPF(params=ModelParams(), N=10, K=4, L=2)
    with pytest.raises((RuntimeError, ValueError)):
        from_rbpf(rbpf)


# ---------------------------------------------------------------------------
# AC: shelf_belief_from_oracle — same public field set from B-state
# ---------------------------------------------------------------------------


def test_shelf_belief_from_oracle_same_public_fields_as_rbpf() -> None:
    from_rbpf = _resolve("shelf_belief_from_rbpf")
    from_oracle = _resolve("shelf_belief_from_oracle")
    rbpf = _stepped_production_rbpf(seed=23)
    from_filter = from_rbpf(rbpf)

    grid = [float(x) for x in age_grid(rbpf.K)]
    # Multi-lot B-state: true counts + ages (point beliefs).
    from_truth = from_oracle(
        lot_counts=[4, 2],
        ages=[1.0, 3.0],
        tau_grid=grid,
    )
    assert _public_field_names(from_filter) == _public_field_names(from_truth)
    assert type(from_truth).__name__ == "ShelfBelief"


def test_shelf_belief_from_oracle_dirac_marginals_on_nearest_grid() -> None:
    from_oracle = _resolve("shelf_belief_from_oracle")
    grid = [0.0, 2.0, 4.0, 6.0]
    belief = from_oracle(lot_counts=[5, 7], ages=[2.0, 6.0], tau_grid=grid)
    margs = _as_nested_floats(belief.age_marginals)
    assert _as_int_list(belief.lot_counts) == [5, 7]
    assert len(margs) == 2
    np.testing.assert_allclose(margs[0], [0.0, 1.0, 0.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(margs[1], [0.0, 0.0, 0.0, 1.0], atol=1e-12)


def test_shelf_belief_from_oracle_rejects_mismatched_lot_and_age_lengths() -> None:
    from_oracle = _resolve("shelf_belief_from_oracle")
    grid = [0.0, 1.0, 2.0]
    with pytest.raises((ValueError, TypeError)):
        from_oracle(lot_counts=[1, 2], ages=[0.5], tau_grid=grid)


def test_shelf_belief_from_oracle_rejects_empty_lots() -> None:
    from_oracle = _resolve("shelf_belief_from_oracle")
    grid = [0.0, 1.0]
    with pytest.raises((ValueError, TypeError)):
        from_oracle(lot_counts=[], ages=[], tau_grid=grid)


# ---------------------------------------------------------------------------
# AC: effective_inventory matches hand-computed SW + pipeline
# ---------------------------------------------------------------------------


def test_effective_inventory_matches_survival_weighted_plus_pipeline() -> None:
    from_oracle = _resolve("shelf_belief_from_oracle")
    effective_inventory = _resolve("effective_inventory")

    params = ModelParams()
    grid = [float(x) for x in age_grid(4)]
    lot_counts = [10, 4]
    # Ages on grid knots → Dirac marginals, SW hand-check is exact.
    ages = [grid[0], grid[2]]
    belief = from_oracle(lot_counts=lot_counts, ages=ages, tau_grid=grid)
    marg = np.asarray(belief.age_marginals, dtype=float)

    on_hand = survival_weighted_on_hand(
        lot_counts,
        marg,
        params=params,
        tau_grid=grid,
        from_marginals=True,
    )
    pending: PendingOrders = {1: 8}  # 8 units arrive in 1 day
    pipeline_w = _flat_prior_expected_survival(params, grid)
    expected = float(on_hand + 8.0 * pipeline_w)

    got = effective_inventory(
        belief,
        pending_orders=pending,
        params=params,
    )
    assert isinstance(got, float)
    assert got == pytest.approx(expected, rel=0.0, abs=1e-9)


def test_effective_inventory_empty_pending_equals_survival_weighted_on_hand() -> None:
    from_oracle = _resolve("shelf_belief_from_oracle")
    effective_inventory = _resolve("effective_inventory")
    params = ModelParams()
    grid = [0.0, 2.0, 4.0]
    belief = from_oracle(lot_counts=[6], ages=[2.0], tau_grid=grid)
    marg = np.asarray(belief.age_marginals, dtype=float)
    on_hand = survival_weighted_on_hand(
        [6],
        marg,
        params=params,
        tau_grid=grid,
        from_marginals=True,
    )
    got = effective_inventory(belief, pending_orders={}, params=params)
    assert got == pytest.approx(float(on_hand), abs=1e-9)


def test_effective_inventory_pipeline_only_when_zero_on_hand() -> None:
    from_oracle = _resolve("shelf_belief_from_oracle")
    effective_inventory = _resolve("effective_inventory")
    params = ModelParams()
    grid = [float(x) for x in age_grid(3)]
    belief = from_oracle(lot_counts=[0], ages=[grid[0]], tau_grid=grid)
    pending: PendingOrders = {1: 12, 2: 4}
    w = _flat_prior_expected_survival(params, grid)
    expected = 12.0 * w + 4.0 * w
    got = effective_inventory(belief, pending_orders=pending, params=params)
    assert got == pytest.approx(expected, abs=1e-9)


def test_effective_inventory_rejects_negative_pending_quantities() -> None:
    from_oracle = _resolve("shelf_belief_from_oracle")
    effective_inventory = _resolve("effective_inventory")
    params = ModelParams()
    grid = [0.0, 1.0]
    belief = from_oracle(lot_counts=[1], ages=[0.0], tau_grid=grid)
    with pytest.raises((ValueError, TypeError)):
        effective_inventory(belief, pending_orders={1: -3}, params=params)


def test_effective_inventory_from_rbpf_preserves_fractional_lot_means() -> None:
    """MF weight-averaged counts are fractional; do not floor before SW (ADR 0092)."""
    from_rbpf = _resolve("shelf_belief_from_rbpf")
    effective_inventory = _resolve("effective_inventory")
    rbpf = _stepped_production_rbpf(seed=11)
    belief = from_rbpf(rbpf)

    counts = [float(x) for x in list(belief.lot_counts)]
    assert any(c != float(int(c)) for c in counts), (
        "fixture must yield non-integer MF means so flooring bias is observable"
    )

    marg = np.asarray(belief.age_marginals, dtype=float)
    grid = [float(t) for t in list(belief.tau_grid)]
    on_hand_float = survival_weighted_on_hand(
        counts,
        marg,
        params=rbpf.params,
        tau_grid=grid,
        from_marginals=True,
    )
    on_hand_floored = survival_weighted_on_hand(
        [int(c) for c in counts],
        marg,
        params=rbpf.params,
        tau_grid=grid,
        from_marginals=True,
    )
    # Flooring biases tilde I_t low vs continuous expectation (~0.75 on N=40).
    assert float(on_hand_float) > float(on_hand_floored)

    pending: PendingOrders = {1: 5}
    pipeline_w = _flat_prior_expected_survival(rbpf.params, grid)
    expected = float(on_hand_float + 5.0 * pipeline_w)
    got = effective_inventory(
        belief,
        pending_orders=pending,
        params=rbpf.params,
    )
    assert got == pytest.approx(expected, rel=0.0, abs=1e-9)
    assert got != pytest.approx(
        float(on_hand_floored + 5.0 * pipeline_w),
        rel=0.0,
        abs=1e-6,
    )


# ---------------------------------------------------------------------------
# AC: CTL path does not need RBPF._state (factory + effective_inventory only)
# ---------------------------------------------------------------------------


def test_ctl_facing_path_does_not_require_rbpf_underscore_state() -> None:
    """Order-relevant inventory via public factory + effective_inventory only."""
    from_rbpf = _resolve("shelf_belief_from_rbpf")
    effective_inventory = _resolve("effective_inventory")
    rbpf = _stepped_production_rbpf(seed=31)

    # CTL-facing code path (this test body): no attribute access to rbpf._state.
    belief = from_rbpf(rbpf)
    inv = effective_inventory(
        belief,
        pending_orders={1: 0},
        params=rbpf.params,
    )
    assert isinstance(inv, float)
    assert inv >= 0.0
    assert not hasattr(belief, "_state")
    # Return type must not be the private particle cloud.
    assert type(belief).__name__ != "ParticleState"


def test_belief_module_public_api_does_not_export_particle_state() -> None:
    mod = importlib.import_module("blueberries_voi.filter.belief")
    assert getattr(mod, "ParticleState", None) is None
    exported = set(getattr(mod, "__all__", ()))
    assert "ParticleState" not in exported
    assert "_state" not in exported


# ---------------------------------------------------------------------------
# AC: JSON-serialisable list/float round-trip (no numpy-only public surface)
# ---------------------------------------------------------------------------


def test_shelf_belief_json_round_trip_list_float_surface() -> None:
    ShelfBelief = _resolve("ShelfBelief")
    from_oracle = _resolve("shelf_belief_from_oracle")
    grid = [0.0, 2.5, 5.0]
    belief = from_oracle(lot_counts=[2, 3], ages=[0.0, 5.0], tau_grid=grid)

    payload = _export_payload(belief)
    # Must be JSON-serialisable without a custom numpy encoder.
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    assert isinstance(decoded, dict)

    restored = _round_trip(ShelfBelief, belief)
    assert _as_int_list(restored.lot_counts) == _as_int_list(belief.lot_counts)
    np.testing.assert_allclose(
        _as_nested_floats(restored.age_marginals),
        _as_nested_floats(belief.age_marginals),
        atol=1e-12,
    )


def test_shelf_belief_public_fields_are_not_numpy_only() -> None:
    from_oracle = _resolve("shelf_belief_from_oracle")
    grid = [0.0, 1.0, 2.0]
    belief = from_oracle(lot_counts=[1], ages=[1.0], tau_grid=grid)
    payload = _export_payload(belief)

    def _assert_jsonable(obj: Any, path: str) -> None:
        if isinstance(obj, (int, float, str, bool)) or obj is None:
            return
        if isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                _assert_jsonable(item, f"{path}[{i}]")
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                _assert_jsonable(v, f"{path}.{k}")
            return
        # numpy scalars/arrays are not an acceptable sole public export surface
        assert not isinstance(obj, np.ndarray), (
            f"{path} is a numpy ndarray; ShelfBelief public/export surface "
            "must be list/float JSON-friendly (ADR 0092)"
        )
        # Allow numpy scalar only if already coerced in export; reject raw np types
        assert not isinstance(obj, np.generic), (
            f"{path} is a numpy scalar; export list/float primitives instead"
        )
        msg = f"{path} has non-JSON type {type(obj)!r}"
        raise AssertionError(msg)

    _assert_jsonable(payload, "export")

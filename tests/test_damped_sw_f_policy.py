"""T-C2-A AC-policy: f-native damped-SW path (production f-wire).

Companion to ``test_damped_sw_policy.py`` (legacy τ path skipped per T-121 F3).
"""

from __future__ import annotations

import importlib

import pytest

_F_GRID = (0.0, 0.5, 1.0)
_F_LOT_COUNTS = (10.0, 5.0)
_F_MARGINALS = (
    0.0,
    1.0,
    0.0,  # lot0: E[f]=0.5
    0.0,
    0.0,
    1.0,  # lot1: E[f]=1.0
)
_F_PENDING: dict[int, int] = {1: 8}
_F_PIPELINE_DEFAULT = 1.0


def _require_belief_export(name: str) -> object:
    mod = importlib.import_module("blueberries_voi.filter.belief")
    obj = getattr(mod, name, None)
    assert obj is not None, f"blueberries_voi.filter.belief must export {name} (T-C2-A)"
    return obj


def _require_f_sw_export(name: str) -> object:
    try:
        mod = importlib.import_module("blueberries_voi.controller.f_sw")
    except ModuleNotFoundError:
        pytest.fail(
            "blueberries_voi.controller.f_sw must exist for f-native damped-SW "
            "(T-C2-A)",
            pytrace=False,
        )
    obj = getattr(mod, name, None)
    assert obj is not None, f"blueberries_voi.controller.f_sw must export {name}"
    return obj


def _f_belief_fixture() -> object:
    shelf_belief_from_f_oracle = _require_belief_export("shelf_belief_from_f_oracle")
    return shelf_belief_from_f_oracle(
        lot_counts=list(_F_LOT_COUNTS),
        f_marginals=[list(_F_MARGINALS[:3]), list(_F_MARGINALS[3:])],
        f_grid=list(_F_GRID),
    )


def _hand_effective_inventory_f(
    *,
    lot_counts: tuple[float, ...],
    f_marginals: tuple[float, ...],
    f_grid: tuple[float, ...],
    pending_orders: dict[int, int],
    f_pipeline_default: float,
) -> float:
    k = len(f_grid)
    n_lots = len(lot_counts)
    on_hand = 0.0
    for ell in range(n_lots):
        e_f = sum(f_marginals[ell * k + b] * f_grid[b] for b in range(k))
        on_hand += lot_counts[ell] * e_f
    pipeline = sum(float(q) * f_pipeline_default for q in pending_orders.values())
    return on_hand + pipeline


def test_f_belief_effective_inventory_matches_ef_weighted_sum() -> None:
    """AC-policy: effective_inventory_f_belief uses E[f] from f_marginals x f_grid."""
    effective_inventory_f_belief = _require_belief_export(
        "effective_inventory_f_belief"
    )

    belief = _f_belief_fixture()
    expected = _hand_effective_inventory_f(
        lot_counts=_F_LOT_COUNTS,
        f_marginals=_F_MARGINALS,
        f_grid=_F_GRID,
        pending_orders=_F_PENDING,
        f_pipeline_default=_F_PIPELINE_DEFAULT,
    )
    assert expected == pytest.approx(18.0)
    got = effective_inventory_f_belief(
        belief,
        pending_orders=_F_PENDING,
        f_pipeline_default=_F_PIPELINE_DEFAULT,
    )
    assert got == pytest.approx(expected)


def test_f_belief_effective_inventory_empty_lots_pipeline_only() -> None:
    effective_inventory_f_belief = _require_belief_export(
        "effective_inventory_f_belief"
    )
    empty_f_shelf_belief = _require_belief_export("empty_f_shelf_belief")

    belief = empty_f_shelf_belief(f_grid=list(_F_GRID))
    got = effective_inventory_f_belief(
        belief,
        pending_orders={0: 4},
        f_pipeline_default=0.75,
    )
    assert got == pytest.approx(3.0)


def test_f_belief_damped_sw_order_matches_hand_formula() -> None:
    """AC-policy: damped_sw_order_f_belief mirrors τ belief structure on f-wire."""
    from scipy.stats import nbinom

    from blueberries_voi.model import ModelParams
    from blueberries_voi.sim.bakeoff_ordering import case_round

    damped_sw_order_f_belief = _require_f_sw_export("damped_sw_order_f_belief")

    belief = _f_belief_fixture()
    params = ModelParams()
    rho, alpha = 0.8, 0.9
    i_tilde = _hand_effective_inventory_f(
        lot_counts=_F_LOT_COUNTS,
        f_marginals=_F_MARGINALS,
        f_grid=_F_GRID,
        pending_orders=_F_PENDING,
        f_pipeline_default=_F_PIPELINE_DEFAULT,
    )
    r = float(params.nb_r()) * 2.0
    p = float(params.nb_p())
    d_star = float(nbinom.ppf(alpha, r, p))
    expected = int(case_round(rho * max(0.0, d_star - i_tilde), params.case_size))
    got = damped_sw_order_f_belief(
        belief,
        pending_orders=_F_PENDING,
        params=params,
        alpha=alpha,
        rho=rho,
        f_pipeline_default=_F_PIPELINE_DEFAULT,
    )
    assert isinstance(got, int)
    assert got >= 0
    assert got % params.case_size == 0
    assert got == expected


def test_f_belief_damped_sw_zero_when_inventory_covers_quantile() -> None:
    from blueberries_voi.model import ModelParams

    damped_sw_order_f_belief = _require_f_sw_export("damped_sw_order_f_belief")
    shelf_belief_from_f_oracle = _require_belief_export("shelf_belief_from_f_oracle")

    belief = shelf_belief_from_f_oracle(
        lot_counts=[200.0],
        f_marginals=[[0.0, 1.0]],
        f_grid=[0.0, 1.0],
    )
    params = ModelParams()
    got = damped_sw_order_f_belief(
        belief,
        pending_orders={},
        params=params,
        alpha=0.9,
        rho=0.8,
        f_pipeline_default=1.0,
    )
    assert got == 0


def test_f_belief_export_uses_f_grid_not_tau_grid() -> None:
    FreshShelfBelief = _require_belief_export("FreshShelfBelief")

    belief = _f_belief_fixture()
    assert isinstance(belief, FreshShelfBelief)
    payload = belief.to_export()
    assert "f_grid" in payload
    assert "f_marginals" in payload
    assert "tau_grid" not in payload
    assert "age_marginals" not in payload
    for f in payload["f_grid"]:
        assert 0.0 <= float(f) <= 1.0

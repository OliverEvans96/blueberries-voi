"""T-139 AC-7: targeted coverage for filter/belief.py helpers."""

from __future__ import annotations

import pytest

from blueberries_voi.filter.belief import (
    ShelfBelief,
    cohort_tau_from_belief_lot,
    effective_inventory,
    empty_shelf_belief,
    flatten_shelf_belief,
    mean_f_from_belief,
    shelf_belief_from_cohorts_oracle,
    shelf_belief_from_oracle,
    unflatten_shelf_belief,
)
from blueberries_voi.model import Cohort


def test_shelf_belief_round_trip_and_effective_inventory() -> None:
    belief = shelf_belief_from_oracle(
        lot_counts=[10.0, 5.0],
        f_marginals=[[0.2, 0.8], [0.5, 0.5]],
        f_grid=[0.25, 0.75],
    )
    payload = flatten_shelf_belief(belief)
    restored = unflatten_shelf_belief(payload)
    assert restored.lot_counts == belief.lot_counts
    assert restored.f_grid == belief.f_grid
    on_hand = effective_inventory(restored, pending_orders={2: 4}, f_pipeline_default=0.9)
    assert on_hand > 0.0


def test_empty_and_cohort_oracle_belief() -> None:
    empty = empty_shelf_belief(f_grid=[0.5, 1.0])
    assert empty.lot_counts == []
    cohorts = [Cohort(n=3, tau=2.0), Cohort(n=0, tau=5.0)]
    from_oracle = shelf_belief_from_cohorts_oracle(
        cohorts, empty_f_grid=[0.5, 0.75, 1.0], eta_ref=14.0
    )
    assert len(from_oracle.lot_counts) == 1
    tau = cohort_tau_from_belief_lot(from_oracle, lot_index=0, eta_ref=14.0)
    assert tau >= 0.0
    mean_f = mean_f_from_belief(from_oracle, lot_index=0)
    assert 0.0 <= mean_f <= 1.0


def test_shelf_belief_validation_errors() -> None:
    with pytest.raises(ValueError, match="lot_counts length"):
        shelf_belief_from_oracle(
            lot_counts=[1.0],
            f_marginals=[[0.5, 0.5], [0.5, 0.5]],
            f_grid=[0.25, 0.75],
        )
    with pytest.raises(ValueError, match="pending_orders"):
        belief = ShelfBelief(lot_counts=[1.0], f_marginals=[[1.0]], f_grid=[0.5])
        effective_inventory(belief, pending_orders={0: -1})

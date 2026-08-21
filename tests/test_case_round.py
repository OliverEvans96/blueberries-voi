"""Case rounding helper retained for sim/viz."""

from __future__ import annotations

import pytest

from blueberries_voi.sim.case_round import case_round


def test_case_round_nearest_multiple() -> None:
    assert case_round(9.0, 8) == 8
    assert case_round(12.0, 8) == 16


def test_case_round_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="case_size"):
        case_round(1.0, 0)
    with pytest.raises(ValueError, match="non-negative"):
        case_round(-1.0, 8)

"""T-036 VOI metric tests (VOI-01)."""

from __future__ import annotations

import pytest

from blueberries_voi.voi import VoIMetric, voi_vs_p0


def test_voi_vs_p0_positive_delta() -> None:
    m = voi_vs_p0(110.0, 100.0)
    assert isinstance(m, VoIMetric)
    assert m.absolute_delta == pytest.approx(10.0)
    assert m.pct_vs_p0 == pytest.approx(0.1)


def test_voi_vs_p0_negative_delta() -> None:
    m = voi_vs_p0(90.0, 100.0)
    assert m.absolute_delta == pytest.approx(-10.0)
    assert m.pct_vs_p0 == pytest.approx(-0.1)


def test_voi_vs_p0_zero_delta() -> None:
    m = voi_vs_p0(50.0, 50.0)
    assert m.absolute_delta == pytest.approx(0.0)
    assert m.pct_vs_p0 == pytest.approx(0.0)


def test_voi_vs_p0_rejects_zero_denominator() -> None:
    with pytest.raises(ValueError, match="profit_p0 is zero"):
        voi_vs_p0(10.0, 0.0)

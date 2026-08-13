"""T-041 / package export smoke for M3 VOI."""

from __future__ import annotations

import blueberries_voi.voi as voi


def test_voi_package_exports_nonempty() -> None:
    assert voi.__all__
    assert "voi_vs_p0" in voi.__all__
    assert "run_voi_sweep" in voi.__all__
    assert "run_voi_crn_cell" in voi.__all__
    assert "paired_bootstrap_ci" in voi.__all__


def test_no_honesty_arm_exports() -> None:
    names = set(voi.__all__)
    assert "misspecification" not in {n.lower() for n in names}
    assert "certainty_equivalence" not in names

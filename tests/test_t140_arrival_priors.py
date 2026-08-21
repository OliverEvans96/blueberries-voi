"""T-140 AC-7: F2a constant removed; calendar pack-date prior uses fleet phi_bar."""

from __future__ import annotations

import inspect


def test_arrival_priors_no_f2a_transit_constant() -> None:
    """RED: F2A_TRANSIT_UNCERTAINTY_SD must be removed from arrival_priors."""
    from blueberries_voi import filter

    src = inspect.getsource(filter.arrival_priors)
    assert "F2A_TRANSIT_UNCERTAINTY_SD" not in src, (
        "RED: drop hand-set F2A_TRANSIT_UNCERTAINTY_SD (ADR 0141)"
    )
    assert "phi_bar" in src.lower() or "calendar" in src.lower(), (
        "RED: arrival_priors must reference phi_bar or calendar pack date"
    )

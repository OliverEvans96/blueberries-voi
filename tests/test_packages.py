"""T-001: ENG-02 package layout is importable."""

from __future__ import annotations


def test_subpackages_importable() -> None:
    import blueberries_voi.controller
    import blueberries_voi.filter
    import blueberries_voi.model
    import blueberries_voi.sim
    import blueberries_voi.viz
    import blueberries_voi.voi  # noqa: F401


def test_runtime_deps_importable() -> None:
    import matplotlib  # noqa: F401
    import numpy  # noqa: F401
    import scipy  # noqa: F401

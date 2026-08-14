"""Golden / skip-if-missing parity vs optional ``blueberries_voi._core``."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("blueberries_voi._core")

from blueberries_voi import _core as rust_core  # noqa: E402
from blueberries_voi.model.physics import weibull_survival  # noqa: E402


def test_weibull_matches_python() -> None:
    py = weibull_survival(3.0, beta=2.0, eta=14.0)
    rs = float(rust_core.weibull_survival_py(3.0, 2.0, 14.0))
    assert math.isclose(py, rs, rel_tol=0.0, abs_tol=1e-12)

"""Golden / skip-if-missing parity vs optional ``blueberries_voi._core``."""

from __future__ import annotations

import math

import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.model.constitutive import weibull_survival

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

rust_core = _maybe_core


def test_weibull_matches_python() -> None:
    py = weibull_survival(3.0, beta=2.0, eta=14.0)
    rs = float(rust_core.weibull_survival_py(3.0, 2.0, 14.0))
    assert math.isclose(py, rs, rel_tol=0.0, abs_tol=1e-12)

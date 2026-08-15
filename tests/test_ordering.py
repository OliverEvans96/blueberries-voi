"""T-026: case_round + ConstantOrderPolicy (CTL ladder floor).

Locks nearest case rounding with an explicit half-away-from-zero tie rule, a
constant-order Policy-shaped primitive, pure controller imports, and package
exports. See `.team/specs/T-026.md`.
"""

from __future__ import annotations

import pytest

pytest.skip("T-121 F3: controller.ordering removed", allow_module_level=True)

import ast
import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from blueberries_voi.model import ModelParams

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ORDERING_MODULE = "blueberries_voi.sim.bakeoff_ordering"
_CONTROLLER_PKG = "blueberries_voi.controller"
_ORDERING_PATH = _REPO_ROOT / "src" / "blueberries_voi" / "controller" / "ordering.py"

# Nearest multiple of case_size; ties (exactly halfway) round half away from
# zero — for non-negative x, toward +∞ (the larger multiple). Locked here per
# T-026 open question; implementer must match this table and document it.
_CASE_ROUND_FIXTURES_CS8: tuple[tuple[float, int], ...] = (
    (0.0, 0),
    (1.0, 0),
    (3.0, 0),
    (3.9, 0),
    (4.0, 8),  # tie 0↔8 → 8
    (4.1, 8),
    (7.9, 8),
    (8.0, 8),
    (8.1, 8),
    (11.9, 8),
    (12.0, 16),  # tie 8↔16 → 16
    (12.1, 16),
    (15.9, 16),
    (16.0, 16),
    (20.0, 24),  # tie 16↔24 → 24
    (24.0, 24),
    (30.0, 32),  # tie 24↔32 → 32
)

_CASE_ROUND_FIXTURES_CS4: tuple[tuple[float, int], ...] = (
    (0.0, 0),
    (1.0, 0),
    (2.0, 4),  # tie 0↔4 → 4
    (3.0, 4),
    (4.0, 4),
    (6.0, 8),  # tie 4↔8 → 8
    (10.0, 12),  # tie 8↔12 → 12
)

_FORBIDDEN_IMPORT_ROOTS = frozenset({"matplotlib", "pyarrow", "pyarrow.parquet"})


def _resolve(attr: str) -> Any:
    try:
        mod = importlib.import_module(_ORDERING_MODULE)
    except ImportError as exc:
        pytest.fail(
            f"{_ORDERING_MODULE} must exist for T-026 ({attr}): {exc}",
            pytrace=False,
        )
    found = getattr(mod, attr, None)
    assert found is not None, (
        f"{attr} must be exported from {_ORDERING_MODULE} (see .team/specs/T-026.md)"
    )
    return found


def _invoke_order(
    policy: Any,
    belief: Any = None,
    *,
    day: int = 0,
    pending_orders: tuple[int, ...] = (),
) -> int:
    """Call Policy-shaped ``order`` with the T-024/T-028-aligned surface."""
    return int(policy.order(belief, day=day, pending_orders=pending_orders))


def test_case_round_fixture_table_default_case_size_matches_model_params() -> None:
    """Default case_size=8 matches ModelParams; fixture table locks nearest+ties."""
    case_round = _resolve("case_round")
    assert ModelParams().case_size == 8
    for x, expected in _CASE_ROUND_FIXTURES_CS8:
        got = case_round(x, 8)
        assert isinstance(got, int), (
            f"case_round({x}, 8) must return int, got {type(got)}"
        )
        assert got == expected, f"case_round({x}, 8) → {got}, expected {expected}"
        assert got % 8 == 0


def test_case_round_uses_model_params_default_when_case_size_omitted() -> None:
    case_round = _resolve("case_round")
    sig = inspect.signature(case_round)
    params = list(sig.parameters.values())
    assert len(params) >= 1
    # Second arg may be optional with default 8, or keyword-only case_size=8.
    if "case_size" in sig.parameters:
        default = sig.parameters["case_size"].default
        assert default == 8
        assert case_round(12.0) == 16
    else:
        # Positional-only (x, case_size=8) still OK if default present.
        assert params[1].default == 8
        assert case_round(12.0) == 16


def test_case_round_fixture_table_case_size_4() -> None:
    case_round = _resolve("case_round")
    for x, expected in _CASE_ROUND_FIXTURES_CS4:
        got = case_round(x, 4)
        assert got == expected, f"case_round({x}, 4) → {got}, expected {expected}"
        assert got % 4 == 0


def test_case_round_result_always_non_negative_multiple() -> None:
    case_round = _resolve("case_round")
    for x in (0.0, 0.1, 4.0, 100.0, 103.5):
        got = case_round(x, 8)
        assert got >= 0
        assert got % 8 == 0


def test_case_round_rejects_non_positive_case_size() -> None:
    case_round = _resolve("case_round")
    with pytest.raises(ValueError):
        case_round(8.0, 0)
    with pytest.raises(ValueError):
        case_round(8.0, -4)


def test_case_round_rejects_negative_x() -> None:
    """Order quantities are non-negative; negative targets are out of domain."""
    case_round = _resolve("case_round")
    with pytest.raises(ValueError):
        case_round(-1.0, 8)
    with pytest.raises(ValueError):
        case_round(-4.0, 8)


def test_ordering_module_docstring_documents_nearest_and_tie_rule() -> None:
    """Rounding mode must be documented on the module (T-026 open question)."""
    _resolve("case_round")
    assert _ORDERING_PATH.is_file(), f"missing {_ORDERING_PATH}"
    mod = importlib.import_module(_ORDERING_MODULE)
    doc = (mod.__doc__ or "").lower()
    assert "nearest" in doc, "module docstring must document nearest rounding"
    assert "tie" in doc or "half" in doc, (
        "module docstring must document the halfway tie rule "
        "(half away from zero / toward +∞ for non-negative x)"
    )


def test_constant_order_policy_returns_fixed_case_rounded_quantity() -> None:
    ConstantOrderPolicy = _resolve("ConstantOrderPolicy")
    case_round = _resolve("case_round")
    policy = ConstantOrderPolicy(10, case_size=8)
    expected = case_round(10, 8)  # 10 → 8 under nearest
    assert expected == 8
    assert _invoke_order(policy) == expected
    assert _invoke_order(policy, object(), day=3, pending_orders=(8, 16)) == expected
    assert _invoke_order(policy, None, day=99, pending_orders=()) == expected


def test_constant_order_policy_default_case_size_is_eight() -> None:
    ConstantOrderPolicy = _resolve("ConstantOrderPolicy")
    case_round = _resolve("case_round")
    policy = ConstantOrderPolicy(12)  # default case_size=8 → 16
    assert _invoke_order(policy) == case_round(12, 8) == 16


def test_constant_order_policy_already_multiple_unchanged() -> None:
    ConstantOrderPolicy = _resolve("ConstantOrderPolicy")
    policy = ConstantOrderPolicy(16, case_size=8)
    assert _invoke_order(policy) == 16
    assert _invoke_order(policy, "belief", day=1, pending_orders=(24,)) == 16


def test_constant_order_policy_zero_orders_zero() -> None:
    ConstantOrderPolicy = _resolve("ConstantOrderPolicy")
    policy = ConstantOrderPolicy(0, case_size=8)
    assert _invoke_order(policy) == 0


def test_constant_order_policy_order_signature_accepts_belief_day_pending() -> None:
    """T-024 Policy surface: belief + day + pending_orders → non-negative int."""
    ConstantOrderPolicy = _resolve("ConstantOrderPolicy")
    policy = ConstantOrderPolicy(8, case_size=8)
    sig = inspect.signature(policy.order)
    names = set(sig.parameters)
    assert "belief" in names or len(sig.parameters) >= 2, (
        "order(...) must accept a belief argument (T-024 Policy)"
    )
    out = _invoke_order(policy, belief={"n": 0}, day=0, pending_orders=())
    assert isinstance(out, int)
    assert out >= 0


def test_controller_ordering_has_no_matplotlib_pyarrow_or_file_writes() -> None:
    """controller/ordering.py must stay a pure library (X-04 / agent brief)."""
    _resolve("case_round")
    assert _ORDERING_PATH.is_file()
    source = _ORDERING_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_ORDERING_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            imported.add(root)
            imported.add(node.module)
    forbidden = imported & _FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, f"controller.ordering imports forbidden: {sorted(forbidden)}"
    # No pathlib Path writes / open() for output in this module.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open":
                pytest.fail("controller.ordering must not call open()", pytrace=False)
            if isinstance(func, ast.Attribute) and func.attr in {
                "write_text",
                "write_bytes",
                "mkdir",
                "touch",
                "dump",
                "savefig",
            }:
                pytest.fail(
                    f"controller.ordering must not write files ({func.attr})",
                    pytrace=False,
                )


def test_controller_package_exports_case_round_and_constant_order_policy() -> None:
    case_round = _resolve("case_round")
    ConstantOrderPolicy = _resolve("ConstantOrderPolicy")
    pkg = importlib.import_module(_CONTROLLER_PKG)
    exported = getattr(pkg, "__all__", None)
    assert isinstance(exported, list)
    assert exported, "controller.__all__ must be non-empty after T-026"
    assert "case_round" in exported
    assert "ConstantOrderPolicy" in exported
    assert getattr(pkg, "case_round", None) is case_round
    assert getattr(pkg, "ConstantOrderPolicy", None) is ConstantOrderPolicy

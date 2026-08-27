"""Guard: pytest must not subprocess ``cargo test`` (kernel tests live in Rust)."""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

# Files that mention the string only in assertions or policy docs.
_ALLOWLIST = frozenset(
    {
        "test_ci_python_job.py",
        "test_no_cargo_subprocess_duplication.py",
        "test_rust_slow_tier.py",
        "_cargo.py",
    }
)


def test_no_pytest_spawns_cargo_test() -> None:
    """Kernel behavior is tested in Rust; pytest must not subprocess cargo test."""
    offenders: list[str] = []
    for path in sorted((_REPO / "tests").glob("test_*.py")):
        if path.name in _ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if "cargo test" in text or '"cargo", "test"' in text:
            offenders.append(path.name)
    assert not offenders, (
        "pytest must not subprocess cargo test; move to Rust or nightly slow tier: "
        + ", ".join(offenders)
    )


def test_cargo_helpers_require_release() -> None:
    """tests/_cargo.py must always pass --release."""
    cargo_py = _REPO / "tests" / "_cargo.py"
    assert cargo_py.is_file(), "tests/_cargo.py must exist"
    text = cargo_py.read_text(encoding="utf-8")
    assert '"--release"' in text
    assert "CARGO_RELEASE" in text

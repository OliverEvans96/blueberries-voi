"""Centralized cargo argv helpers — release-only Rust policy."""

from __future__ import annotations

CARGO_RELEASE = ("--release", "--locked")


def cargo_test_argv(*extra: str) -> list[str]:
    """Return argv for ``cargo test`` on voi_core in release profile."""
    return ["cargo", "test", *CARGO_RELEASE, "-p", "voi_core", *extra]

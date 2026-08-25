"""Smoke helpers for shipment fixtures (ADR 0107 edge fill)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueberries_voi.sim.shipments import (
    default_shipments,
    ensure_demo_shipments,
    smoke_cool_shipments,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_smoke_cool_shipments_returns_one_trace() -> None:
    ships = smoke_cool_shipments()
    assert len(ships) == 1
    assert ships[0].shipment_id == "SMOKE-COOL"


def test_ensure_demo_shipments_fills_missing() -> None:
    out = ensure_demo_shipments({})
    assert out["shipments"]
    assert len(out["shipments"]) == 1


def test_ensure_demo_shipments_fills_empty_list() -> None:
    out = ensure_demo_shipments({"shipments": []})
    assert len(out["shipments"]) == 1


def test_ensure_demo_shipments_preserves_nonempty() -> None:
    existing = smoke_cool_shipments()
    out = ensure_demo_shipments({"shipments": existing})
    assert out["shipments"] is existing


def test_default_shipments_delegates_to_mod21_demo(
    monkeypatch: MonkeyPatch,
) -> None:
    import blueberries_voi.sim.shipments as shipments_mod

    sentinel = smoke_cool_shipments()
    monkeypatch.setattr(
        shipments_mod, "mod21_demo_shipments", lambda product="abdella_all": sentinel
    )
    assert default_shipments() is sentinel

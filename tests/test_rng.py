"""T-001: SIM-05 SeedSequence spawn API."""

from __future__ import annotations

import numpy as np

from blueberries_voi import rng as bv_rng


def test_known_streams_importable() -> None:
    assert bv_rng.STREAM_DEMAND == ":demand"
    assert bv_rng.STREAM_SPOIL == ":spoil"
    assert bv_rng.STREAM_ALLOC == ":alloc"
    assert bv_rng.STREAM_ARRIVAL_SHIP == ":arrival_ship"
    assert bv_rng.STREAM_ARRIVAL_SENSOR == ":arrival_sensor"
    assert bv_rng.STREAM_FILTER_RESAMPLE == ":filter_resample"
    assert bv_rng.STREAM_BIRTH == ":birth"


def test_same_slot_bit_identical() -> None:
    a = bv_rng.spawn_rng(42, run_id="r0", day=3, stream=bv_rng.STREAM_DEMAND)
    b = bv_rng.spawn_rng(42, run_id="r0", day=3, stream=bv_rng.STREAM_DEMAND)
    assert np.array_equal(a.random(20), b.random(20))


def test_different_streams_differ() -> None:
    d = bv_rng.spawn_rng(42, run_id="r0", day=3, stream=bv_rng.STREAM_DEMAND)
    s = bv_rng.spawn_rng(42, run_id="r0", day=3, stream=bv_rng.STREAM_SPOIL)
    assert not np.array_equal(d.random(20), s.random(20))


def test_demand_consumption_does_not_desync_spoil() -> None:
    spoil_a = bv_rng.spawn_rng(7, run_id=1, day=0, stream=bv_rng.STREAM_SPOIL)
    ref = spoil_a.random(10)

    # Consume many demand draws first (simulating unequal draw counts across arms).
    demand = bv_rng.spawn_rng(7, run_id=1, day=0, stream=bv_rng.STREAM_DEMAND)
    _ = demand.random(500)

    spoil_b = bv_rng.spawn_rng(7, run_id=1, day=0, stream=bv_rng.STREAM_SPOIL)
    assert np.array_equal(spoil_b.random(10), ref)


def test_unknown_stream_raises() -> None:
    try:
        bv_rng.spawn_rng(1, run_id="x", day=0, stream=":nope")
    except ValueError as exc:
        assert "unknown stream" in str(exc)
    else:
        raise AssertionError("expected ValueError")

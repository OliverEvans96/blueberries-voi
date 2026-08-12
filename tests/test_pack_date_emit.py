"""T-019: sim emits ASN pack_date on DayLog so F2a Stage A can contract.

RED / acceptance contracts. No production changes in this ticket's RED phase.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np

from blueberries_voi.filter.arrival_priors import (
    cold_abdella_arrival_age_prior,
    delivery_birth_age_prior,
)
from blueberries_voi.filter.types import (
    UNOBSERVED,
    age_grid,
    mask_for,
    rich_obs_from_day_log,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import EpisodeLog, run_episode
from blueberries_voi.viz import m15

_REPO = Path(__file__).resolve().parents[1]
_ABDELLA = _REPO / "data" / "abdella"


def _episode(
    *,
    root_seed: int = 19,
    run_id: str = "t019",
    n_burn: int = 5,
    n_score: int = 20,
) -> EpisodeLog:
    ships = load_abdella_shipments(_ABDELLA)
    return run_episode(
        ModelParams(),
        root_seed=root_seed,
        run_id=run_id,
        n_burn=n_burn,
        n_score=n_score,
        shipments=ships,
    )


def _spread(weights: np.ndarray, grid: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    g = np.asarray(grid, dtype=float)
    w = w / max(float(w.sum()), 1e-300)
    mean = float(np.sum(g * w))
    var = float(np.sum(w * (g - mean) ** 2))
    return float(np.sqrt(max(var, 0.0)))


def test_delivery_daylog_emits_real_pack_date() -> None:
    """AC: delivery days expose a real ``date`` pack_date (not None / not zero)."""
    ep = _episode()
    saw_delivery = False
    for d in ep.days:
        if d.arrivals <= 0:
            continue
        saw_delivery = True
        assert d.pack_date is not None, (
            "T-019: delivery DayLog must emit ASN pack_date (Oliver-approved); "
            f"got None on day={d.day} arrivals={d.arrivals}"
        )
        assert isinstance(d.pack_date, date)
        # FIL-08: missing != zero — a real date is never a numeric sentinel.
        assert d.pack_date != 0
        assert d.age_at_receipt is not None
    assert saw_delivery, "fixture episode must include at least one delivery day"


def test_non_delivery_daylog_pack_date_remains_none() -> None:
    """AC: non-delivery days leave pack_date None (do not invent a date)."""
    ep = _episode(root_seed=20)
    saw_non = False
    for d in ep.days:
        if d.arrivals != 0:
            continue
        saw_non = True
        assert d.pack_date is None, (
            f"non-delivery day={d.day} must leave pack_date None, got {d.pack_date!r}"
        )
        assert d.age_at_receipt is None
    assert saw_non, "fixture episode must include a non-delivery day"


def test_pack_date_crn_stable_across_identical_runs() -> None:
    """AC: shared CRN → identical pack_date sequence for identical seeds."""
    a = _episode(root_seed=21, run_id="crn")
    b = _episode(root_seed=21, run_id="crn")
    packs_a = [d.pack_date for d in a.days]
    packs_b = [d.pack_date for d in b.days]
    assert packs_a == packs_b
    assert [d.age_at_receipt for d in a.days] == [d.age_at_receipt for d in b.days]
    # Must not pass vacuously while every pack_date is still None.
    assert any(p is not None for p in packs_a), (
        "CRN lock requires at least one emitted pack_date on a delivery day"
    )


def test_f2a_mask_observes_sim_pack_date_p0_p1_do_not() -> None:
    """AC: F2a RichObs sees sim pack_date; P0/P1 leave it UNOBSERVED (FIL-08 masks)."""
    ep = _episode(root_seed=22)
    delivery = next(d for d in ep.days if d.arrivals > 0)
    assert delivery.pack_date is not None, (
        "sim must emit pack_date before mask projection"
    )

    f2a = rich_obs_from_day_log(delivery, mask_for("F2a"))
    p0 = rich_obs_from_day_log(delivery, mask_for("P0"))
    p1 = rich_obs_from_day_log(delivery, mask_for("P1"))

    assert f2a.pack_date == delivery.pack_date
    assert f2a.age_at_receipt is UNOBSERVED  # F2a mask: pack_date only, not age
    assert p0.pack_date is UNOBSERVED
    assert p1.pack_date is UNOBSERVED


def test_f2a_birth_prior_from_sim_daylog_narrower_than_cold() -> None:
    """AC: sim→F2a obs birth prior SD strictly < cold Abdella mix."""
    ep = _episode(root_seed=23)
    delivery = next(d for d in ep.days if d.arrivals > 0)
    assert delivery.pack_date is not None

    params = ModelParams()
    grid = age_grid(8)
    obs = rich_obs_from_day_log(delivery, mask_for("F2a"))
    birth = delivery_birth_age_prior(obs, grid, params)
    cold = cold_abdella_arrival_age_prior(grid, params)

    assert _spread(birth, grid) < _spread(cold, grid), (
        "F2a birth prior from sim-emitted pack_date must be narrower than cold mix"
    )


def test_stage_a_f2a_contracts_when_pack_date_emitted(tmp_path: Path) -> None:
    """AC: run_m15_stage_a F2a rung reports contracted=True under smoke defaults."""
    result = m15.run_m15_stage_a(
        root_seed=0,
        rungs=("F2a",),
        contraction_margin=0.05,
        figures_dir=tmp_path,
        write_figure=False,
    )
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.scenario == "F2a"
    assert row.contracted is True, (
        "T-019: Stage A F2a must contract once sim emits pack_date; "
        f"prior_sd={row.prior_sd:.4f} posterior_sd={row.posterior_sd:.4f} "
        f"(still blocked if DayLog.pack_date is always None)"
    )

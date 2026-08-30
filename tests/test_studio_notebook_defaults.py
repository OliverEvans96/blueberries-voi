"""Studio-aligned defaults for notebook / Modal BO pipelines (abdella_mix + P&L)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueberries_voi.experiments.channel_joint import run_seed_channel_joint
from blueberries_voi.experiments.damped_sw_soo import DampedSwSooBudgets
from blueberries_voi.experiments.voi_profit import profit_session_config
from blueberries_voi.filter.types import ObsChannels
from blueberries_voi.sim.profit import (
    DEFAULT_STORE_ECONOMICS,
    STUDIO_PROFIT_COSTS,
    ProfitCosts,
    profit_costs_from_store_economics,
)
from blueberries_voi.sim.shipments import (
    DEFAULT_ARRIVAL_PRODUCT,
    default_shipments,
    mod21_demo_shipments,
)

if TYPE_CHECKING:
    import pytest


def test_default_arrival_product_is_abdella_mix() -> None:
    assert DEFAULT_ARRIVAL_PRODUCT == "abdella_mix"


def test_default_shipments_use_abdella_mix_product_key() -> None:
    ships = default_shipments()
    expected = mod21_demo_shipments("abdella_mix")
    assert len(ships) == len(expected)
    assert [s.duration_d for s in ships] == [s.duration_d for s in expected]


def test_studio_profit_costs_match_web_mock_defaults() -> None:
    econ = DEFAULT_STORE_ECONOMICS
    costs = profit_costs_from_store_economics(econ)
    assert costs == STUDIO_PROFIT_COSTS
    assert costs.unit_margin == econ.sell_price - econ.purchase_cost
    assert costs.waste_cost == DEFAULT_STORE_ECONOMICS.waste_cost
    assert costs.stockout_penalty == DEFAULT_STORE_ECONOMICS.stockout_penalty
    assert costs.unit_margin == 2.7
    assert costs.waste_cost == 1.2
    assert costs.stockout_penalty == 2.5


def test_channel_joint_defaults_to_studio_profit_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[ProfitCosts] = []

    def _fake_day_profit(_log: object, costs: ProfitCosts) -> float:
        captured.append(costs)
        return 0.0

    monkeypatch.setattr(
        "blueberries_voi.experiments.channel_joint.day_profit",
        _fake_day_profit,
    )
    run_seed_channel_joint(
        42,
        ObsChannels(code_type="upc", scan_waste=False, delivery_history="none"),
        n_burn=0,
        n_score=1,
    )
    assert captured
    assert captured[0] == STUDIO_PROFIT_COSTS


def test_profit_session_config_wires_abdella_mix_arrival() -> None:
    cfg = profit_session_config()
    assert cfg.get("arrival_product") == "abdella_mix"
    ships = cfg.get("shipments")
    assert ships is not None
    assert len(ships) == len(mod21_demo_shipments("abdella_mix"))


def test_damped_sw_soo_budgets_carry_arrival_product() -> None:
    budgets = DampedSwSooBudgets(
        n_burn=14,
        n_score=45,
        lead_time=1,
        unit_margin=2.7,
        waste_cost=1.2,
        stockout_penalty=2.5,
        demand_mu=30.0,
        demand_vm=2.0,
        case_size=8,
        use_calendar_demand=True,
        demand_profile_path="data/freshnet/demand_profile.json",
        arrival_product="abdella_mix",
    )
    payload = budgets.to_dict()
    assert payload["arrival_product"] == "abdella_mix"
    assert "use_abdella" not in payload

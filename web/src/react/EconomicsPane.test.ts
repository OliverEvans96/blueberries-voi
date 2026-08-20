/**
 * T-127 (economics-implement): EconomicsPane — consolidated P&L summary + cumulative chart.
 */
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import type { DayPnL, ViewModel } from "../types";
import { EconomicsPane, mountEconomicsPnLChart } from "./EconomicsPane";

const FIXTURE_SERIES: DayPnL[] = [
  {
    day: 1,
    revenue: 10,
    cost_purchase: 2,
    cost_waste: 1,
    cost_stockout: 0,
    cost_total: 3,
    profit: 7,
  },
  {
    day: 2,
    revenue: 20,
    cost_purchase: 4,
    cost_waste: 0,
    cost_stockout: 1,
    cost_total: 5,
    profit: 15,
  },
];

function baseVm(): Pick<ViewModel, "pnl_totals" | "pnl_series"> {
  return {
    pnl_totals: {
      revenue: 30,
      cost: 8,
      profit: 22,
      today_revenue: 20,
      today_cost: 5,
      today_profit: 15,
    },
    pnl_series: FIXTURE_SERIES,
  };
}

describe("EconomicsPane (T-127 economics-implement)", () => {
  it("renders economics section with P&L summary and pricing host", () => {
    render(createElement(EconomicsPane, { vm: baseVm() as ViewModel }));

    expect(screen.getByRole("region", { name: /economics/i })).toBeInTheDocument();
    expect(document.querySelector('[data-testid="pnl-consolidated"]')).not.toBeNull();
    expect(document.querySelector("#economics-pricing-host")).not.toBeNull();
    expect(screen.getByText(/Revenue: 30/)).toBeInTheDocument();
    expect(screen.getByText(/Profit: 22/)).toBeInTheDocument();
  });

  it("rounds P&L totals to two decimals", () => {
    const vm = baseVm();
    vm.pnl_totals = {
      ...vm.pnl_totals!,
      revenue: 30.4567,
      cost: 8.1,
      profit: 22.3567,
    };
    render(createElement(EconomicsPane, { vm: vm as ViewModel }));

    expect(screen.getByText("Revenue: 30.46")).toBeInTheDocument();
    expect(screen.getByText("Cost: 8.10")).toBeInTheDocument();
    expect(screen.getByText("Profit: 22.36")).toBeInTheDocument();
  });

  it("mounts cumulative P&L chart via ref callback", () => {
    render(createElement(EconomicsPane, { vm: baseVm() as ViewModel }));

    const host = document.querySelector("#chart-pnl-economics");
    expect(host).not.toBeNull();
    const svg = host?.querySelector("svg.chart-svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("aria-label")).toBe(
      "Cumulative revenue, cost, and profit over days",
    );
    expect(host?.querySelector("path.pnl-line.series-revenue")).not.toBeNull();
    expect(host?.querySelector("path.pnl-line.series-cost")).not.toBeNull();
    expect(host?.querySelector("path.pnl-line.series-profit")).not.toBeNull();
  });

  it("mountEconomicsPnLChart delegates to renderPnLTimeseries", () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 480,
      configurable: true,
    });
    mountEconomicsPnLChart(container, FIXTURE_SERIES, 140);
    expect(container.querySelector("svg.chart-svg")).not.toBeNull();
  });
});

/**
 * @vitest-environment jsdom
 *
 * Cumulative PnL transform + render wiring for sparkline / focus charts.
 */
import { describe, expect, it } from "vitest";
import type { DayPnL } from "../types";
import { cumulativePnLSeries, renderPnLTimeseries } from "./pnlTimeseries";

const DAILY: DayPnL[] = [
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
  {
    day: 3,
    revenue: 5,
    cost_purchase: 1,
    cost_waste: 2,
    cost_stockout: 0,
    cost_total: 3,
    profit: 2,
  },
];

describe("cumulativePnLSeries", () => {
  it("accumulates revenue, cost_total, and profit over days", () => {
    const cum = cumulativePnLSeries(DAILY);
    expect(cum).toHaveLength(3);
    expect(cum[0]).toMatchObject({
      day: 1,
      revenue: 10,
      cost_total: 3,
      profit: 7,
    });
    expect(cum[1]).toMatchObject({
      day: 2,
      revenue: 30,
      cost_total: 8,
      profit: 22,
    });
    expect(cum[2]).toMatchObject({
      day: 3,
      revenue: 35,
      cost_total: 11,
      profit: 24,
    });
  });

  it("final cumulative profit equals sum of daily profits", () => {
    const cum = cumulativePnLSeries(DAILY);
    const sumDaily = DAILY.reduce((s, d) => s + d.profit, 0);
    expect(cum[cum.length - 1]!.profit).toBe(sumDaily);
    expect(cum[cum.length - 1]!.profit).toBe(
      cum[cum.length - 1]!.revenue - cum[cum.length - 1]!.cost_total,
    );
  });

  it("returns empty for empty input", () => {
    expect(cumulativePnLSeries([])).toEqual([]);
  });
});

describe("renderPnLTimeseries cumulative wiring", () => {
  it("plots cumulative line paths without per-day dots (T-128 lines-only)", () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 400,
      configurable: true,
    });

    renderPnLTimeseries(container, DAILY, 140);

    const svg = container.querySelector("svg.chart-svg");
    expect(svg?.getAttribute("aria-label")).toBe(
      "Cumulative revenue, cost, and profit over days",
    );

    const profitPath = container.querySelector("path.pnl-line.series-profit");
    expect(profitPath).not.toBeNull();
    const cumD = profitPath!.getAttribute("d");
    expect(cumD).toBeTruthy();

    const dots = container.querySelectorAll(".pnl-dot");
    expect(dots).toHaveLength(0);

    expect(cumD!.length).toBeGreaterThan(10);
  });
});

/**
 * T-127 Primary: sales vs demand stockout gap shading.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { Day } from "../types";
import { CHART_MARGIN } from "../hoverLink";
import { buildDemandForecastRows } from "./demandDist";
import { MIN_CHART_DAY_SPAN } from "./axisTicks";
import { renderSalesDemand, salesDemandX, setSalesDemandHover } from "./salesDemand";

function sampleDay(
  day: number,
  sales: number,
  demand: number,
): Day {
  return {
    day,
    lots: [],
    sales_total: sales,
    waste_total: 0,
    demand,
    order_qty: 0,
    arrivals: 0,
    stockout: Math.max(0, demand - sales),
    f_at_receipt: null,
  };
}

function host(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 400 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("renderSalesDemand stockout gap (T-127)", () => {
  it("renders chart-svg with sales and demand lines", () => {
    const el = host();
    renderSalesDemand(el, [
      sampleDay(0, 8, 10),
      sampleDay(1, 12, 12),
    ]);
    expect(el.querySelector("svg.chart-svg")).not.toBeNull();
    expect(el.querySelector(".sd-sales")).not.toBeNull();
    expect(el.querySelector(".sd-demand")).not.toBeNull();
  });

  it("shades red gap area when demand exceeds sales", () => {
    const el = host();
    renderSalesDemand(el, [
      sampleDay(0, 5, 10),
      sampleDay(1, 12, 12),
      sampleDay(2, 3, 9),
    ]);
    const gap = el.querySelector(".sales-demand-gap");
    expect(gap).not.toBeNull();
    expect(gap?.getAttribute("fill")).toMatch(/rgba?\(.*\)/);
    expect(gap?.getAttribute("d")).toBeTruthy();
  });

  it("omits gap path when demand never exceeds sales", () => {
    const el = host();
    renderSalesDemand(el, [
      sampleDay(0, 10, 8),
      sampleDay(1, 12, 12),
    ]);
    expect(el.querySelector(".sales-demand-gap")).toBeNull();
  });

  it("setSalesDemandHover shows vertical rule for hovered day", () => {
    const el = host();
    renderSalesDemand(el, [sampleDay(0, 5, 10), sampleDay(1, 8, 8)]);
    setSalesDemandHover(el, 0);
    expect(el.querySelector(".hover-rule")?.getAttribute("opacity")).toBe("1");
    setSalesDemandHover(el, null);
    expect(el.querySelector(".hover-rule")?.getAttribute("opacity")).toBe("0");
  });
});

function xAxisDaySpan(el: HTMLElement): number {
  const ticks = [...el.querySelectorAll(".axis-x .tick text")].map((t) =>
    Number(t.textContent),
  );
  if (ticks.length === 0) return 0;
  return Math.max(...ticks) - Math.min(...ticks) + 1;
}

describe("renderSalesDemand min day span (T-151)", () => {
  it("pads x-axis to at least MIN_CHART_DAY_SPAN days with short history", () => {
    const el = host();
    renderSalesDemand(el, [sampleDay(0, 5, 10), sampleDay(1, 8, 8)]);
    expect(xAxisDaySpan(el)).toBeGreaterThanOrEqual(MIN_CHART_DAY_SPAN);
    const innerW = 400 - 40 - CHART_MARGIN.right;
    const hitW = Number(el.querySelector(".day-hit")?.getAttribute("width"));
    expect(hitW).toBeCloseTo(innerW / MIN_CHART_DAY_SPAN, 4);
  });

  it("renders empty 5-day frame when history is empty", () => {
    const el = host();
    renderSalesDemand(el, []);
    expect(el.querySelector("svg.chart-svg")).not.toBeNull();
    expect(xAxisDaySpan(el)).toBeGreaterThanOrEqual(MIN_CHART_DAY_SPAN);
  });
});

describe("renderSalesDemand narrow plot (T-139)", () => {
  it("skips draw when innerW <= 0", () => {
    const el = document.createElement("div");
    Object.defineProperty(el, "clientWidth", { configurable: true, value: 40 });
    document.body.appendChild(el);
    renderSalesDemand(el, [sampleDay(0, 5, 10), sampleDay(1, 8, 8)]);
    expect(el.querySelector("svg.chart-svg")).toBeNull();
  });

  it("uses non-negative day-hit widths when squeezed", () => {
    const el = document.createElement("div");
    Object.defineProperty(el, "clientWidth", { configurable: true, value: 80 });
    document.body.appendChild(el);
    renderSalesDemand(el, [sampleDay(0, 5, 10), sampleDay(1, 8, 8), sampleDay(2, 3, 9)]);
    for (const rect of el.querySelectorAll(".day-hit")) {
      expect(Number(rect.getAttribute("width"))).toBeGreaterThanOrEqual(0);
    }
  });

  it("salesDemandX never returns negative x for negative innerW", () => {
    expect(salesDemandX([0, 1, 2], -10, 1)).toBeGreaterThanOrEqual(0);
  });
});

const FORECAST_SUMMARY = {
  scale_mu: 30,
  dow_means: [29, 30, 28, 26, 28, 34, 35],
};

describe("renderSalesDemand forecast overlay", () => {
  it("renders forecast band and mean with 5 forecast rows", () => {
    const el = host();
    const forecast = buildDemandForecastRows(3, FORECAST_SUMMARY, 2);
    expect(forecast).toHaveLength(5);
    renderSalesDemand(el, [sampleDay(0, 8, 10), sampleDay(1, 12, 12)], 130, forecast);
    expect(el.querySelector(".sd-forecast-band")).not.toBeNull();
    expect(el.querySelector(".sd-forecast-mean")).not.toBeNull();
    expect(el.querySelector(".sd-forecast-today")).not.toBeNull();
  });

  it("x-axis spans through last forecast day", () => {
    const el = host();
    const forecast = buildDemandForecastRows(2, FORECAST_SUMMARY, 2);
    const lastForecastDay = forecast[forecast.length - 1]!.day;
    renderSalesDemand(el, [sampleDay(0, 5, 10), sampleDay(1, 8, 8)], 130, forecast);
    const ticks = [...el.querySelectorAll(".axis-x .tick text")].map((t) =>
      Number(t.textContent),
    );
    expect(Math.max(...ticks)).toBeGreaterThanOrEqual(lastForecastDay);
  });

  it("yMax accommodates p90 above historical demand", () => {
    const history = [
      sampleDay(0, 5, 10),
      sampleDay(1, 8, 12),
      sampleDay(2, 3, 9),
    ];
    const forecast = buildDemandForecastRows(5, FORECAST_SUMMARY, 2);
    const maxP90 = Math.max(...forecast.map((r) => r.p90));
    expect(maxP90).toBeGreaterThan(12);

    const without = host();
    renderSalesDemand(without, history, 130, []);
    const yMaxWithout = Math.max(
      ...[...without.querySelectorAll(".axis-y .tick text")].map((t) =>
        Number(t.textContent),
      ),
    );

    const withForecast = host();
    renderSalesDemand(withForecast, history, 130, forecast);
    const yMaxWith = Math.max(
      ...[...withForecast.querySelectorAll(".axis-y .tick text")].map((t) =>
        Number(t.textContent),
      ),
    );

    expect(yMaxWith).toBeGreaterThan(yMaxWithout);
    const bandD =
      withForecast.querySelector(".sd-forecast-band")?.getAttribute("d") ?? "";
    expect(bandD.length).toBeGreaterThan(0);
  });

  it("legend includes forecast entries when forecast is present", () => {
    const el = host();
    const forecast = buildDemandForecastRows(0, FORECAST_SUMMARY, 2);
    renderSalesDemand(el, [sampleDay(0, 5, 10)], 130, forecast);
    const labels = [...el.querySelectorAll(".legend-label")].map((t) => t.textContent);
    expect(labels).toContain("Forecast μ");
    expect(labels).toContain("p10–p90");
  });
});

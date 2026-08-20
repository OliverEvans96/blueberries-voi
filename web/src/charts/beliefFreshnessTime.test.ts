/**
 * T-127 Primary: freshness×time heatmap + truth overlay.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { BeliefHistoryDay, Day } from "../types";
import {
  BELIEF_FRESHNESS_TIME_MARGIN,
  buildBeliefFreshnessHeatmap,
  renderBeliefFreshnessTime,
  setBeliefFreshnessTimeHover,
} from "./beliefFreshnessTime";

function sampleDay(day: number, lots: Day["lots"]): Day {
  return {
    day,
    lots,
    sales_total: 10,
    waste_total: 1,
    demand: 12,
    order_qty: 8,
    arrivals: 8,
    stockout: 2,
    f_at_receipt: 1,
  };
}

function beliefHistory(days: number[]): BeliefHistoryDay[] {
  return days.map((day, i) => ({
    day,
    flatBelief: {
      L: 1,
      K: 3,
      lot_counts: [10 + i],
      f_marginals: [0.2, 0.5, 0.3],
      f_grid: [0.2, 0.5, 0.8],
    },
  }));
}

function host(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 720 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("beliefFreshnessTime heatmap (T-127)", () => {
  it("renders interpolated belief cells and axes", () => {
    const el = host();
    const history = [
      sampleDay(0, []),
      sampleDay(1, []),
      sampleDay(2, []),
    ];
    renderBeliefFreshnessTime(
      el,
      history,
      beliefHistory([0, 1, 2]),
      false,
      { width: 720, height: 220 },
    );
    expect(el.querySelector("svg.chart-svg")).not.toBeNull();
    expect(el.querySelectorAll(".belief-freshness-cell").length).toBeGreaterThan(
      3,
    );
    expect(el.querySelector(".axis-x")).not.toBeNull();
    expect(el.querySelector(".axis-y")).not.toBeNull();
  });

  it("sub-day interpolation produces more day samples than raw belief days", () => {
    const series = beliefHistory([0, 1, 2]).map((b) => ({
      day: b.day,
      f_edges: [0, 0.33, 0.66, 1],
      marginal: [2, 5, 3],
    }));
    const cells = buildBeliefFreshnessHeatmap(series, 4, 2);
    const uniqueDays = new Set(cells.map((c) => c.day));
    expect(uniqueDays.size).toBeGreaterThan(series.length);
  });

  it("clamps heatmap cell freshness edges to [0, 1] even when input f_edges overshoot", () => {
    const series = [
      { day: 0, f_edges: [-0.1, 0.3, 0.7, 1.1], marginal: [2, 5, 3] },
    ];
    const cells = buildBeliefFreshnessHeatmap(series, 1, 4);
    for (const cell of cells) {
      expect(cell.f0).toBeGreaterThanOrEqual(0);
      expect(cell.f1).toBeLessThanOrEqual(1);
    }
  });

  it("caps the freshness y-axis at 1.0 even when f_grid touches the boundary or truth mean_f exceeds it", () => {
    const el = host();
    renderBeliefFreshnessTime(
      el,
      [sampleDay(0, [{ lot_id: 1, n: 8, mean_f: 1.4 }])],
      [
        {
          day: 0,
          flatBelief: {
            L: 1,
            K: 3,
            lot_counts: [10],
            f_marginals: [0.2, 0.5, 0.3],
            f_grid: [0, 0.5, 1],
          },
        },
      ],
      true,
      { width: 720, height: 220 },
    );
    const tickValues = [...el.querySelectorAll(".axis-y .tick text")].map((t) =>
      Number(t.textContent),
    );
    expect(tickValues.length).toBeGreaterThan(0);
    expect(Math.max(...tickValues)).toBeLessThanOrEqual(1);
  });

  it("draws zero lot circles when showTruth is false", () => {
    const el = host();
    renderBeliefFreshnessTime(
      el,
      [sampleDay(0, [{ lot_id: 1, n: 8, mean_f: 0.7 }])],
      beliefHistory([0]),
      false,
      { width: 720, height: 220 },
    );
    expect(el.querySelectorAll("circle.lot").length).toBe(0);
    expect(el.querySelectorAll(".lot-connection").length).toBe(0);
  });

  it("draws lot dots and connecting lines when showTruth is true", () => {
    const el = host();
    renderBeliefFreshnessTime(
      el,
      [
        sampleDay(0, [{ lot_id: 1, n: 8, mean_f: 0.85 }]),
        sampleDay(1, [{ lot_id: 1, n: 6, mean_f: 0.72 }]),
      ],
      beliefHistory([0, 1]),
      true,
      { width: 720, height: 220 },
    );
    expect(el.querySelectorAll("circle.lot").length).toBe(2);
    expect(el.querySelectorAll(".lot-connection").length).toBe(1);
    const c0 = el.querySelector("circle.lot");
    expect(c0?.getAttribute("cx")).toBeTruthy();
    expect(c0?.getAttribute("cy")).toBeTruthy();
  });

  it("lot radius scales with survivor count n", () => {
    const el = host();
    renderBeliefFreshnessTime(
      el,
      [
        sampleDay(0, [
          { lot_id: 1, n: 4, mean_f: 0.5 },
          { lot_id: 2, n: 16, mean_f: 0.6 },
        ]),
      ],
      beliefHistory([0]),
      true,
      { width: 720, height: 220 },
    );
    const titles = [...el.querySelectorAll("circle.lot title")].map((t) =>
      t.textContent ?? "",
    );
    expect(titles.some((t) => t.includes("qty 4"))).toBe(true);
    expect(titles.some((t) => t.includes("qty 16"))).toBe(true);
  });

  it("setBeliefFreshnessTimeHover toggles hover rule without throwing", () => {
    const el = host();
    renderBeliefFreshnessTime(
      el,
      [sampleDay(0, []), sampleDay(1, [])],
      beliefHistory([0, 1]),
      false,
      { width: 720, height: 220 },
    );
    setBeliefFreshnessTimeHover(el, 0);
    const rule = el.querySelector(".hover-rule");
    expect(rule?.getAttribute("opacity")).toBe("1");
    setBeliefFreshnessTimeHover(el, null);
    expect(rule?.getAttribute("opacity")).toBe("0");
  });

  it("clips heatmap, places y-axis label in gutter, and renders units colorbar", () => {
    const el = host();
    const history = [
      sampleDay(0, []),
      sampleDay(1, []),
      sampleDay(2, []),
    ];
    renderBeliefFreshnessTime(
      el,
      history,
      beliefHistory([0, 1, 2]),
      false,
      { width: 720, height: 220 },
    );

    const svg = el.querySelector("svg.chart-svg");
    expect(svg?.getAttribute("data-margin-left")).toBe(
      String(BELIEF_FRESHNESS_TIME_MARGIN.left),
    );
    expect(svg?.getAttribute("data-margin-right")).toBe(
      String(BELIEF_FRESHNESS_TIME_MARGIN.right),
    );

    expect(el.querySelector(`clipPath#${"belief-freshness-plot-clip"}`)).not.toBeNull();
    expect(el.querySelector(".belief-freshness-colorbar")).not.toBeNull();
    expect(el.querySelector(".belief-freshness-colorbar-label")?.textContent).toBe(
      "Units",
    );

    const gradient = el.querySelector(
      "linearGradient#belief-freshness-colorbar-grad",
    );
    expect(gradient?.querySelectorAll("stop").length).toBe(4);

    const margin = BELIEF_FRESHNESS_TIME_MARGIN;
    const innerH = 220 - margin.top - margin.bottom;
    const yLabels = [...el.querySelectorAll(".axis-label")];
    const freshnessLabel = yLabels.find((n) => n.textContent === "Freshness f");
    expect(freshnessLabel).not.toBeNull();
    expect(Number(freshnessLabel?.getAttribute("y"))).toBe(innerH / 2);
    expect(Number(freshnessLabel?.getAttribute("x"))).toBe(-40);
  });
});

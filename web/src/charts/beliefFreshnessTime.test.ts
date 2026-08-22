/**
 * T-127 Primary: freshness×time heatmap + truth overlay.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { BeliefHistoryDay, Day, Unit, UnitExit } from "../types";
import {
  BELIEF_FRESHNESS_TIME_MARGIN,
  buildBeliefFreshnessHeatmap,
  renderBeliefFreshnessTime,
  setBeliefFreshnessTimeHover,
  unitTerminalDots,
  UNIT_TERMINAL_SOLD,
  UNIT_TERMINAL_SPOILED,
} from "./beliefFreshnessTime";

function sampleDay(
  day: number,
  units: Unit[],
  unitExits: UnitExit[] = [],
): Day {
  return {
    day,
    lots: [],
    units,
    unit_exits: unitExits,
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

  it("caps the freshness y-axis at 1.0 even when f_grid touches the boundary or truth f exceeds it", () => {
    const el = host();
    renderBeliefFreshnessTime(
      el,
      [sampleDay(0, [{ unit_id: 0, lot_id: 1, f: 1.4 }])],
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

  it("draws zero unit trajectories when showTruth is false", () => {
    const el = host();
    renderBeliefFreshnessTime(
      el,
      [sampleDay(0, [{ unit_id: 0, lot_id: 1, f: 0.7 }])],
      beliefHistory([0]),
      false,
      { width: 720, height: 220 },
    );
    expect(el.querySelectorAll(".unit-trajectory").length).toBe(0);
    expect(el.querySelectorAll(".lot").length).toBe(0);
    expect(el.querySelectorAll(".lot-connection").length).toBe(0);
  });

  it("draws unit trajectory paths when showTruth is true", () => {
    const el = host();
    renderBeliefFreshnessTime(
      el,
      [
        sampleDay(0, [{ unit_id: 1, lot_id: 1, f: 0.85 }]),
        sampleDay(1, [{ unit_id: 1, lot_id: 1, f: 0.72 }]),
      ],
      beliefHistory([0, 1]),
      true,
      { width: 720, height: 220 },
    );
    expect(el.querySelectorAll(".unit-trajectory").length).toBe(1);
    expect(el.querySelectorAll(".lot").length).toBe(0);
    expect(el.querySelectorAll(".lot-connection").length).toBe(0);
    const path = el.querySelector(".unit-trajectory");
    expect(path?.getAttribute("d")).toBeTruthy();
    expect(path?.getAttribute("stroke")).toBe("#f97316");
    expect(path?.getAttribute("stroke-width")).toBe("0.75");
    expect(Number(path?.getAttribute("stroke-opacity"))).toBeCloseTo(0.4, 5);
    expect(path?.getAttribute("fill")).toBe("none");
  });

  it("draws terminal dots for sold and spoiled unit exits with legend", () => {
    const el = host();
    renderBeliefFreshnessTime(
      el,
      [
        sampleDay(0, [{ unit_id: 1, lot_id: 1, f: 0.85 }]),
        sampleDay(
          1,
          [],
          [
            { unit_id: 1, lot_id: 1, f: 0.72, cause: "sold" },
            { unit_id: 2, lot_id: 1, f: 0.4, cause: "spoiled" },
          ],
        ),
      ],
      beliefHistory([0, 1]),
      true,
      { width: 720, height: 220 },
    );
    expect(el.querySelectorAll(".unit-terminal").length).toBe(2);
    const sold = el.querySelector(".unit-terminal--sold");
    const spoiled = el.querySelector(".unit-terminal--spoiled");
    expect(sold?.getAttribute("fill")).toBe(UNIT_TERMINAL_SOLD);
    expect(spoiled?.getAttribute("fill")).toBe("#c026d3");
    expect(sold?.getAttribute("fill")).toBe("#0891b2");
    expect(Number(sold?.getAttribute("r"))).toBeCloseTo(1.25, 5);
    const legend = el.querySelector(".belief-freshness-truth-legend");
    expect(legend).not.toBeNull();
    expect(legend?.parentElement?.classList.contains("chart-root")).toBe(false);
    expect(legend?.getAttribute("transform")).toContain("translate(48, 3)");
  });

  it("unitTerminalDots flattens history unit_exits with day index", () => {
    const dots = unitTerminalDots([
      sampleDay(2, [], [{ unit_id: 3, lot_id: 1, f: 0.5, cause: "sold" }]),
    ]);
    expect(dots).toEqual([
      { day: 2, unit_id: 3, lot_id: 1, f: 0.5, cause: "sold" },
    ]);
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
    const freshnessLabel = el.querySelector(".axis-label-y");
    expect(freshnessLabel).not.toBeNull();
    expect(freshnessLabel?.textContent).toBe("Freshness f");
    expect(freshnessLabel?.getAttribute("transform")).toContain("rotate(-90)");
    expect(freshnessLabel?.getAttribute("transform")).toContain(
      String(innerH / 2),
    );
    expect(freshnessLabel?.getAttribute("transform")).toContain("-36");
  });
});

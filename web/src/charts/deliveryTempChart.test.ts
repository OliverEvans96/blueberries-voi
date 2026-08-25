// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { CHART_PAPER, oklabDistance } from "./beliefFreshnessPalette";
import {
  DELIVERY_TEMP_COLOR_STOPS,
  formatTempC,
  lotColor,
  LOT_COLORS,
  renderDeliveryTempHistorySvg,
  renderDeliveryTempMultiLot,
  tempColorScale,
  tempSummaryFromTrace,
  tracesFromEvent,
} from "./deliveryTempChart";

describe("tracesFromEvent", () => {
  it("prefers temp_traces_by_lot when present", () => {
    const traces = tracesFromEvent({
      arrivals: 8,
      temp_traces_by_lot: [
        {
          lot_id: 301,
          times_d: [-2, -1, 0],
          temps_c: [2, 2.2, 2.4],
        },
        {
          lot_id: 302,
          times_d: [-2, -1, 0],
          temps_c: [2.5, 2.7, 2.9],
        },
      ],
    });
    expect(traces).toEqual([
      { lotId: 301, times_d: [-2, -1, 0], temps_c: [2, 2.2, 2.4] },
      { lotId: 302, times_d: [-2, -1, 0], temps_c: [2.5, 2.7, 2.9] },
    ]);
  });

  it("falls back to legacy temp_times_d / temp_temps_c", () => {
    const traces = tracesFromEvent({
      arrivals: 8,
      arrival_lot_ids: [401],
      temp_times_d: [-3, -2, -1, 0],
      temp_temps_c: [2, 2.2, 2.4, 2.6],
    });
    expect(traces).toEqual([
      {
        lotId: 401,
        times_d: [-3, -2, -1, 0],
        temps_c: [2, 2.2, 2.4, 2.6],
      },
    ]);
  });

  it("returns an empty array when no temperature data exists", () => {
    expect(tracesFromEvent({ arrivals: 4 })).toEqual([]);
  });
});

describe("tempSummaryFromTrace", () => {
  it("computes min / max / mean / std from finite temps", () => {
    const summary = tempSummaryFromTrace({
      lotId: 301,
      times_d: [-3, -2, -1, 0],
      temps_c: [2, 2.2, 2.4, 2.6],
    });
    expect(summary).toEqual({
      min: 2,
      max: 2.6,
      mean: 2.3,
      std: expect.closeTo(0.2582, 4),
      n: 4,
    });
  });

  it("uses zero std when fewer than two finite temps", () => {
    const summary = tempSummaryFromTrace({
      lotId: 1,
      times_d: [0],
      temps_c: [2.5],
    });
    expect(summary).toEqual({
      min: 2.5,
      max: 2.5,
      mean: 2.5,
      std: 0,
      n: 1,
    });
  });

  it("returns null when no finite temps exist", () => {
    expect(
      tempSummaryFromTrace({
        lotId: 1,
        times_d: [0],
        temps_c: [Number.NaN],
      }),
    ).toBeNull();
  });
});

describe("formatTempC", () => {
  it("formats one decimal place with a degree symbol", () => {
    expect(formatTempC(2.34)).toBe("2.3°C");
  });
});

describe("lotColor", () => {
  it("cycles through LOT_COLORS", () => {
    expect(lotColor(0)).toBe(LOT_COLORS[0]);
    expect(lotColor(LOT_COLORS.length)).toBe(LOT_COLORS[0]);
  });
});

describe("renderDeliveryTempHistorySvg", () => {
  it("renders axis lines and temperature-colored segments", () => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    renderDeliveryTempHistorySvg(svg, [
      { t: -3, temp: 1 },
      { t: -2, temp: 3 },
      { t: -1, temp: 5 },
      { t: 0, temp: 2 },
    ]);
    expect(svg.querySelector(".delivery-temp-bg")).not.toBeNull();
    expect(svg.querySelector(".delivery-temp-axis-x")).not.toBeNull();
    expect(svg.querySelector(".delivery-temp-axis-y")).not.toBeNull();
    const segments = svg.querySelectorAll(".delivery-temp-segment");
    expect(segments.length).toBeGreaterThan(0);
    const strokes = new Set(
      Array.from(segments).map((el) => el.getAttribute("stroke")),
    );
    expect(strokes.size).toBeGreaterThan(1);
  });
});

describe("tempColorScale (OKLab contrast)", () => {
  it("keeps cold and warm endpoint stops readable on chart paper", () => {
    const color = tempColorScale(0, 6);
    for (const stop of DELIVERY_TEMP_COLOR_STOPS) {
      expect(oklabDistance(stop, CHART_PAPER)).toBeGreaterThanOrEqual(18);
    }
    expect(oklabDistance(color(0), CHART_PAPER)).toBeGreaterThanOrEqual(18);
    expect(oklabDistance(color(6), CHART_PAPER)).toBeGreaterThanOrEqual(18);
  });
});

describe("renderDeliveryTempMultiLot", () => {
  const sampleTraces = [
    {
      lotId: 301,
      times_d: [-3, -2, -1, 0],
      temps_c: [2, 2.2, 2.4, 2.6],
    },
    {
      lotId: 302,
      times_d: [-3, -2, -1, 0],
      temps_c: [2.5, 2.7, 2.9, 3.1],
    },
  ];

  it("defaults height to 48", () => {
    const host = document.createElement("div");
    Object.defineProperty(host, "clientWidth", { value: 280, configurable: true });
    renderDeliveryTempMultiLot(host, sampleTraces);
    expect(host.querySelector("svg")?.getAttribute("viewBox")).toMatch(/ 48$/);
  });

  it("renders axis lines and temperature-colored segments per lot", () => {
    const host = document.createElement("div");
    Object.defineProperty(host, "clientWidth", { value: 280, configurable: true });
    renderDeliveryTempMultiLot(host, sampleTraces);
    const svg = host.querySelector("svg");
    expect(svg?.querySelector(".delivery-temp-bg")).not.toBeNull();
    expect(svg?.querySelector(".delivery-temp-axis-x")).not.toBeNull();
    expect(svg?.querySelector(".delivery-temp-axis-y")).not.toBeNull();
    const segments = svg?.querySelectorAll(".delivery-temp-segment") ?? [];
    expect(segments.length).toBeGreaterThan(0);
    const strokes = new Set(
      Array.from(segments).map((el) => el.getAttribute("stroke")),
    );
    expect(strokes.size).toBeGreaterThan(1);
    expect(svg?.querySelectorAll('[data-lot="301"]').length).toBeGreaterThan(0);
    expect(svg?.querySelectorAll('[data-lot="302"]').length).toBeGreaterThan(0);
  });

  it("keeps lot-colored legend swatches for multi-lot traces", () => {
    const host = document.createElement("div");
    Object.defineProperty(host, "clientWidth", { value: 280, configurable: true });
    renderDeliveryTempMultiLot(host, sampleTraces);
    const legendLines = host.querySelectorAll(".delivery-temp-legend line");
    expect(legendLines.length).toBe(2);
    expect(legendLines[0]?.getAttribute("stroke")).toBe(LOT_COLORS[0]);
    expect(legendLines[1]?.getAttribute("stroke")).toBe(LOT_COLORS[1]);
  });
});

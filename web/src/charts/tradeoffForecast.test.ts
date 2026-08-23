/**
 * T-127 RED (qa-tradeoff-ui): tradeoff chart renderers — bands and histogram lookup.
 */
// @vitest-environment jsdom
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const CURVE = join(HERE, "tradeoffCurve.ts");
const HIST = join(HERE, "tradeoffHistogram.ts");

type QForecast = {
  q: number;
  waste_mean: number;
  waste_p10: number;
  waste_p50: number;
  waste_p90: number;
  missed_mean: number;
  missed_p10: number;
  missed_p50: number;
  missed_p90: number;
  joint_hist: {
    waste_bins: number[];
    missed_bins: number[];
    counts: number[][];
  };
};

const CANDIDATES: QForecast[] = [
  {
    q: 0,
    waste_mean: 1,
    waste_p10: 0,
    waste_p50: 1,
    waste_p90: 3,
    missed_mean: 8,
    missed_p10: 5,
    missed_p50: 8,
    missed_p90: 12,
    joint_hist: { waste_bins: [0, 2], missed_bins: [0, 10], counts: [[1, 0], [0, 1]] },
  },
  {
    q: 16,
    waste_mean: 2,
    waste_p10: 1,
    waste_p50: 2,
    waste_p90: 5,
    missed_mean: 4,
    missed_p10: 2,
    missed_p50: 4,
    missed_p90: 7,
    joint_hist: { waste_bins: [0, 3], missed_bins: [0, 7], counts: [[0, 1], [1, 0]] },
  },
];

import type { QForecastEntry } from "./tradeoffCurve";
import {
  nearestCandidateQ,
  renderTradeoffCurve as renderTradeoffCurveSvg,
  tradeoffXExtent,
  tradeoffYExtent,
} from "./tradeoffCurve";
import { renderTradeoffHistogram as renderTradeoffHistogramSvg } from "./tradeoffHistogram";

async function loadCurve() {
  return {
    renderTradeoffCurve: renderTradeoffCurveSvg,
    nearestCandidateQ,
  };
}

async function loadHist() {
  return { renderTradeoffHistogram: renderTradeoffHistogramSvg };
}

function flatForecast(q: number, value: number): QForecastEntry {
  return {
    q,
    waste_mean: value,
    waste_p10: value,
    waste_p50: value,
    waste_p90: value,
    missed_mean: value,
    missed_p10: value,
    missed_p50: value,
    missed_p90: value,
    joint_hist: { waste_bins: [0, 1], missed_bins: [0, 1], counts: [[1]] },
  };
}

function flatSweep(value: number, count = 20): QForecastEntry[] {
  return Array.from({ length: count }, (_, i) => flatForecast(i * 8, value));
}

function yAxisTickYs(svg: SVGSVGElement): number[] {
  return Array.from(svg.querySelectorAll(".axis-y g.tick"))
    .map((g) => {
      const transform = g.getAttribute("transform") ?? "";
      const match = /translate\(0,([^)]+)\)/.exec(transform);
      return match ? Number(match[1]) : NaN;
    })
    .filter((y) => Number.isFinite(y));
}

function firstPathY(d: string | null | undefined): number {
  const match = /^M[^,]+,([0-9.]+)/.exec(d ?? "");
  return match ? Number(match[1]) : NaN;
}

describe("tradeoff chart modules (T-127 AC-tradeoff-ui)", () => {
  it("exports renderTradeoffCurve", async () => {
    const mod = await loadCurve();
    expect(mod?.renderTradeoffCurve).toBeTypeOf("function");
  });

  it("exports renderTradeoffHistogram", async () => {
    const mod = await loadHist();
    expect(mod?.renderTradeoffHistogram).toBeTypeOf("function");
  });

  it("nearestCandidateQ picks closest q on drag lookup", async () => {
    const mod = await loadCurve();
    expect(mod?.nearestCandidateQ).toBeTypeOf("function");
    expect(mod!.nearestCandidateQ(CANDIDATES, 15)).toBe(16);
    expect(mod!.nearestCandidateQ(CANDIDATES, 8)).toBe(0);
  });

  it("renderTradeoffCurve draws band paths (p10-p90)", async () => {
    const mod = await loadCurve();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mod!.renderTradeoffCurve(svg, CANDIDATES, 16);
    expect(svg.querySelector(".tradeoff-band-waste, [data-band='waste']")).not.toBeNull();
    expect(svg.querySelector(".tradeoff-band-missed, [data-band='missed']")).not.toBeNull();
    expect(svg.querySelector("[data-order-q='16'], .order-marker")).not.toBeNull();
  });

  it("renderTradeoffCurve draws a legend for waste and missed sales bands", async () => {
    const mod = await loadCurve();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mod!.renderTradeoffCurve(svg, CANDIDATES, 16);
    expect(svg.querySelector(".tradeoff-curve-legend")).not.toBeNull();
    const labels = Array.from(svg.querySelectorAll(".legend-label")).map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["Waste", "Missed sales"]);
  });

  it("renderTradeoffCurve draws waste_mean and missed_mean line overlays", async () => {
    const mod = await loadCurve();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mod!.renderTradeoffCurve(svg, CANDIDATES, 16);
    const wasteMean = svg.querySelector(
      ".tradeoff-mean-waste, [data-series='waste_mean']",
    );
    const missedMean = svg.querySelector(
      ".tradeoff-mean-missed, [data-series='missed_mean']",
    );
    expect(wasteMean).not.toBeNull();
    expect(missedMean).not.toBeNull();
    expect(wasteMean?.getAttribute("stroke")).toBe("var(--missed, #c44)");
    expect(missedMean?.getAttribute("stroke")).toBe("var(--sales, #48a)");
    expect(wasteMean?.getAttribute("d")).toBeTruthy();
    expect(missedMean?.getAttribute("d")).toBeTruthy();
  });

  it("tradeoffXExtent avoids zero-width domain for empty or single-q data", () => {
    expect(tradeoffXExtent([])).toEqual([0, 1]);
    expect(tradeoffXExtent([flatForecast(24, 0)])).toEqual([23.5, 24.5]);
  });

  it("tradeoffYExtent avoids zero-width domain when all values are zero", () => {
    const extent = tradeoffYExtent(flatSweep(0));
    expect(extent[1] - extent[0]).toBeGreaterThan(0);
    expect(extent[0]).toBeLessThan(0);
    expect(extent[1]).toBeGreaterThan(0);
  });

  it("tradeoffYExtent pads flat non-zero forecasts around the value", () => {
    const extent = tradeoffYExtent(flatSweep(10_000));
    expect(extent[0]).toBeLessThan(10_000);
    expect(extent[1]).toBeGreaterThan(10_000);
  });

  it("renderTradeoffCurve spreads y-axis ticks when forecasts are flat at zero", async () => {
    const mod = await loadCurve();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mod!.renderTradeoffCurve(svg, flatSweep(0), 24, 300, 0.7);
    const tickYs = yAxisTickYs(svg);
    expect(tickYs.length).toBeGreaterThan(2);
    expect(Math.max(...tickYs) - Math.min(...tickYs)).toBeGreaterThan(10);
    const missedD = svg.querySelector(".tradeoff-mean-missed")?.getAttribute("d");
    expect(missedD).not.toMatch(/NaN/);
  });

  it("renderTradeoffCurve centers flat-at-zero series instead of pinning to the axis", async () => {
    const mod = await loadCurve();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mod!.renderTradeoffCurve(svg, flatSweep(0), 24, 300, 0.7);
    const innerH = 140 - 16 - 32;
    const y = firstPathY(
      svg.querySelector(".tradeoff-mean-missed")?.getAttribute("d"),
    );
    expect(y).toBeGreaterThan(innerH * 0.25);
    expect(y).toBeLessThan(innerH * 0.75);
  });

  it("renderTradeoffCurve does not emit NaN marker positions before forecasts load", async () => {
    const mod = await loadCurve();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mod!.renderTradeoffCurve(svg, [], 24, 300, 0.7);
    const marker = svg.querySelector(".order-q-marker");
    expect(marker?.getAttribute("x1")).not.toBe("NaN");
    expect(marker?.getAttribute("x2")).not.toBe("NaN");
  });

  it("renderTradeoffCurve centers flat non-zero series instead of pinning to the top", async () => {
    const mod = await loadCurve();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mod!.renderTradeoffCurve(svg, flatSweep(10_000), 24, 300, 0.7);
    const innerH = 140 - 16 - 32;
    const y = firstPathY(
      svg.querySelector(".tradeoff-mean-missed")?.getAttribute("d"),
    );
    expect(y).toBeGreaterThan(innerH * 0.25);
    expect(y).toBeLessThan(innerH * 0.75);
  });

  it("renderTradeoffHistogram selects joint_hist for nearest q", async () => {
    const mod = await loadHist();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const nearest = CANDIDATES[1]!;
    mod!.renderTradeoffHistogram(svg, nearest.joint_hist, 16);
    expect(svg.querySelector("rect, .hist-cell")).not.toBeNull();
  });
});

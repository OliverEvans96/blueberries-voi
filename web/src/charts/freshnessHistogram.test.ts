/**
 * Secondary pane: aggregate belief + truth histogram overlays (~8 bars).
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { FlatBelief } from "../engine/types";
import type { Lot, Unit } from "../types";
import {
  aggregateBeliefMasses,
  binIndexForValue,
  DISPLAY_BIN_COUNT,
  emptyFreshnessHistogramData,
  freshnessHistogramDataFromFlat,
  histogramEdges,
  rebinMasses,
  rebinMassesByInterval,
  renderFreshnessHistogram,
  truthMassesFromUnits,
  truthMassesInBins,
  type FreshnessHistogramData,
} from "./freshnessHistogram";

const TRUTH_UNITS: Unit[] = [
  { unit_id: 0, lot_id: 1, f: 0.85 },
  { unit_id: 1, lot_id: 1, f: 0.84 },
  { unit_id: 2, lot_id: 1, f: 0.86 },
  { unit_id: 3, lot_id: 2, f: 0.55 },
  { unit_id: 4, lot_id: 2, f: 0.54 },
  { unit_id: 5, lot_id: 3, f: 0.35 },
  { unit_id: 6, lot_id: 3, f: 0.36 },
  { unit_id: 7, lot_id: 3, f: 0.34 },
  { unit_id: 8, lot_id: 3, f: 0.33 },
  { unit_id: 9, lot_id: 1, f: 0.87 },
];

const FLAT: FlatBelief = {
  L: 3,
  K: 4,
  lot_counts: [10, 6, 4],
  f_grid: [0.125, 0.375, 0.625, 0.875],
  f_marginals: [
    1, 0, 0, 0,
    0, 1, 0, 0,
    0, 0, 1, 0,
  ],
};

function host(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 420 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("aggregateBeliefMasses", () => {
  it("sums per-lot mass into one bin vector", () => {
    const masses = aggregateBeliefMasses(FLAT);
    expect(masses).toHaveLength(FLAT.K);
    expect(masses[0]).toBeCloseTo(10);
    expect(masses[1]).toBeCloseTo(6);
    expect(masses[2]).toBeCloseTo(4);
  });
});

describe("DISPLAY_BIN_COUNT", () => {
  it("uses eight evenly spaced display bins on [0, 1]", () => {
    expect(DISPLAY_BIN_COUNT).toBe(8);
    expect(histogramEdges(0, 1, DISPLAY_BIN_COUNT)).toHaveLength(9);
  });
});

describe("rebinMasses / rebinMassesByInterval / truthMassesInBins / truthMassesFromUnits", () => {
  it("rebins source masses into display bins (point assignment)", () => {
    const edges = histogramEdges(0, 1, DISPLAY_BIN_COUNT);
    const rebinned = rebinMasses(FLAT.f_grid, aggregateBeliefMasses(FLAT), edges);
    expect(rebinned).toHaveLength(DISPLAY_BIN_COUNT);
    expect(rebinned.reduce((a, b) => a + b, 0)).toBeCloseTo(20);
  });

  it("interval rebin assigns non-zero mass to center display bin for FLAT", () => {
    const data = freshnessHistogramDataFromFlat(FLAT);
    const edges = histogramEdges(0, 1, DISPLAY_BIN_COUNT);
    const rebinned = rebinMassesByInterval(
      data.f_edges,
      data.belief_masses,
      edges,
    );
    expect(rebinned.reduce((a, b) => a + b, 0)).toBeCloseTo(20);
    const centerIdx = binIndexForValue(edges, 0.5625);
    expect(rebinned[centerIdx]).toBeGreaterThan(0);
    const byPoint = rebinMasses(data.f_centers, data.belief_masses, edges);
    expect(byPoint[centerIdx]).toBeCloseTo(0);
  });

  it("assigns truth lot counts by mean_f bin", () => {
    const edges = histogramEdges(0, 1, DISPLAY_BIN_COUNT);
    const lots: Lot[] = [
      { lot_id: 1, n: 10, mean_f: 0.85 },
    ];
    const truth = truthMassesInBins(lots, edges);
    expect(truth.reduce((a, b) => a + b, 0)).toBeCloseTo(10);
    expect(truth[binIndexForValue(edges, 0.85)]).toBeCloseTo(10);
  });

  it("counts each live unit at its f bin", () => {
    const edges = histogramEdges(0, 1, DISPLAY_BIN_COUNT);
    const truth = truthMassesFromUnits(TRUTH_UNITS, edges);
    expect(truth.reduce((a, b) => a + b, 0)).toBeCloseTo(TRUTH_UNITS.length);
    expect(truth[binIndexForValue(edges, 0.85)]).toBeCloseTo(4);
    expect(truth[binIndexForValue(edges, 0.35)]).toBeCloseTo(4);
  });
});

describe("freshnessHistogramDataFromFlat", () => {
  it("maps flat belief into aggregate bin masses", () => {
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_UNITS);
    expect(data.f_edges).toHaveLength(FLAT.K + 1);
    expect(data.f_centers).toEqual(FLAT.f_grid);
    expect(data.belief_masses[0]).toBeCloseTo(10);
    expect(data.belief_masses[1]).toBeCloseTo(6);
    expect(data.belief_masses[2]).toBeCloseTo(4);
    expect(data.truth_units).toEqual(TRUTH_UNITS);
  });
});

describe("renderFreshnessHistogram", () => {
  it("renders ~8 belief bars with yellow fill and semi-bold caps", () => {
    const el = host();
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_UNITS);
    renderFreshnessHistogram(el, data, false, 260);

    const svg = el.querySelector("svg");
    expect(svg).not.toBeNull();
    const bars = el.querySelectorAll(".freshness-belief-bar");
    expect(bars.length).toBeGreaterThan(0);
    expect(bars.length).toBeLessThanOrEqual(DISPLAY_BIN_COUNT);
    expect(bars[0]?.getAttribute("fill")).toBe("#e6b800");
    expect(bars[0]?.getAttribute("fill-opacity")).toBe("0.25");
    expect(el.querySelectorAll(".freshness-belief-cap").length).toBe(bars.length);
    expect(el.querySelectorAll(".freshness-truth-bar").length).toBe(0);
  });

  it("draws truth bars only when showTruth is true", () => {
    const elOff = host();
    const elOn = host();
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_UNITS);

    renderFreshnessHistogram(elOff, data, false, 260);
    renderFreshnessHistogram(elOn, data, true, 260);

    expect(elOff.querySelectorAll(".freshness-truth-bar").length).toBe(0);
    expect(elOn.querySelectorAll(".freshness-truth-bar").length).toBeGreaterThan(0);
    expect(elOn.querySelectorAll(".freshness-belief-bar").length).toBeGreaterThan(0);
    expect(elOn.querySelector(".freshness-truth-bar")?.getAttribute("fill")).toBe("#2563eb");
  });

  it("legend shows Belief and Truth only (no per-lot labels)", () => {
    const el = host();
    const data: FreshnessHistogramData = {
      f_edges: [0, 0.5, 1],
      f_centers: [0.25, 0.75],
      belief_masses: [8, 2],
      truth_units: [{ unit_id: 0, lot_id: 1, f: 0.2 }],
    };
    renderFreshnessHistogram(el, data, true, 260);

    const labels = [...el.querySelectorAll(".legend-label")].map(
      (node) => node.textContent,
    );
    expect(labels).toEqual(["Belief", "Truth"]);
    expect(labels.some((label) => label?.startsWith("Lot"))).toBe(false);
  });

  it("empty scaffold renders fixed-height SVG with axes", () => {
    const el = host();
    const height = 150;
    renderFreshnessHistogram(el, emptyFreshnessHistogramData(), true, height);
    const svg = el.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("height")).toBe(String(height));
    expect(el.querySelectorAll(".axis").length).toBeGreaterThan(0);
    expect(el.querySelectorAll(".freshness-belief-bar").length).toBe(0);
  });
});

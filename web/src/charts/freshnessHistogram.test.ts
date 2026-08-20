/**
 * Secondary pane: aggregate belief + truth KDE overlays.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { FlatBelief } from "../engine/types";
import type { Lot } from "../types";
import {
  aggregateBeliefMasses,
  beliefKdeFromFlat,
  defaultBandwidth,
  freshnessHistogramDataFromFlat,
  renderFreshnessHistogram,
  truthKdeFromLots,
  weightedGaussianKde,
  type FreshnessHistogramData,
} from "./freshnessHistogram";

const TRUTH_LOTS: Lot[] = [
  { lot_id: 1, n: 10, mean_f: 0.85 },
  { lot_id: 2, n: 6, mean_f: 0.55 },
  { lot_id: 3, n: 4, mean_f: 0.35 },
];

const FLAT: FlatBelief = {
  L: 3,
  K: 4,
  lot_counts: [10, 6, 4],
  f_grid: [0.125, 0.375, 0.625, 0.875],
  f_marginals: [
    1, 0, 0, 0,
    0, 1, 0, 0,
    0, 0, 0, 1,
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
    expect(masses[3]).toBeCloseTo(4);
  });
});

describe("weightedGaussianKde", () => {
  it("preserves total mass under the curve", () => {
    const xGrid = [0, 0.25, 0.5, 0.75, 1];
    const samples = [
      { x: 0.2, weight: 5 },
      { x: 0.8, weight: 3 },
    ];
    const bw = 0.1;
    const densities = weightedGaussianKde(samples, xGrid, bw);
    const dx = xGrid[1]! - xGrid[0]!;
    const area = densities.reduce((sum, d) => sum + d * dx, 0);
    expect(area).toBeCloseTo(8, 0);
  });
});

describe("defaultBandwidth", () => {
  it("derives bandwidth from bin edges", () => {
    const bw = defaultBandwidth([0, 0.25, 0.5, 0.75, 1]);
    expect(bw).toBeGreaterThan(0);
    expect(bw).toBeCloseTo(0.375);
  });
});

describe("freshnessHistogramDataFromFlat", () => {
  it("maps flat belief into aggregate bin masses", () => {
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_LOTS);
    expect(data.f_edges).toHaveLength(FLAT.K + 1);
    expect(data.f_centers).toEqual(FLAT.f_grid);
    expect(data.belief_masses[0]).toBeCloseTo(10);
    expect(data.belief_masses[1]).toBeCloseTo(6);
    expect(data.belief_masses[3]).toBeCloseTo(4);
    expect(data.truth_lots).toEqual(TRUTH_LOTS);
  });
});

describe("beliefKdeFromFlat / truthKdeFromLots", () => {
  it("peaks near concentrated belief and truth mass", () => {
    const xGrid = [0, 0.125, 0.375, 0.625, 0.875, 1];
    const f_edges = [0, 0.25, 0.5, 0.75, 1];
    const belief = beliefKdeFromFlat(FLAT, xGrid);
    const truth = truthKdeFromLots(TRUTH_LOTS, xGrid, f_edges);
    expect(belief[1]).toBeGreaterThan(belief[3]!);
    const truthPeakIdx = truth.indexOf(Math.max(...truth));
    expect(xGrid[truthPeakIdx]).toBeGreaterThan(0.5);
  });
});

describe("renderFreshnessHistogram", () => {
  it("renders belief KDE path (no stacked bars)", () => {
    const el = host();
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_LOTS);
    renderFreshnessHistogram(el, data, false, 260);

    const svg = el.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(el.querySelector(".freshness-belief-kde")).not.toBeNull();
    expect(el.querySelectorAll(".freshness-stack-segment").length).toBe(0);
    expect(el.querySelectorAll(".truth-bar").length).toBe(0);
  });

  it("draws truth KDE only when showTruth is true", () => {
    const elOff = host();
    const elOn = host();
    const data = freshnessHistogramDataFromFlat(FLAT, TRUTH_LOTS);

    renderFreshnessHistogram(elOff, data, false, 260);
    renderFreshnessHistogram(elOn, data, true, 260);

    expect(elOff.querySelectorAll(".freshness-truth-kde").length).toBe(0);
    expect(elOn.querySelectorAll(".freshness-truth-kde").length).toBe(1);
    expect(elOn.querySelectorAll(".freshness-belief-kde").length).toBe(1);
  });

  it("legend shows Belief and Truth only (no per-lot labels)", () => {
    const el = host();
    const data: FreshnessHistogramData = {
      f_edges: [0, 0.5, 1],
      f_centers: [0.25, 0.75],
      belief_masses: [8, 2],
      truth_lots: [{ lot_id: 1, n: 5, mean_f: 0.2 }],
    };
    renderFreshnessHistogram(el, data, true, 260);

    const labels = [...el.querySelectorAll(".legend-label")].map(
      (node) => node.textContent,
    );
    expect(labels).toEqual(["Belief", "Truth"]);
    expect(labels.some((label) => label?.startsWith("Lot"))).toBe(false);
  });
});

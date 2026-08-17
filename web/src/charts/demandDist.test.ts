/**
 * T-127: picking variability curve + projected demand helpers.
 */
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import {
  pickingWeightsF,
  pickingWeightCurve,
  projectedDemandDays,
  renderDemandDist,
  renderPickingVariability,
} from "./demandDist";

describe("pickingWeightsF (physics::picking_weights_f parity)", () => {
  it("returns uniform weights when sigma <= 0", () => {
    const w = pickingWeightsF([0.2, 0.5, 0.9], 0);
    expect(w).toEqual([1 / 3, 1 / 3, 1 / 3]);
  });

  it("weights proportional to f^sigma and sum to 1", () => {
    const f = [0.2, 0.5, 0.9];
    const sigma = 0.5;
    const w = pickingWeightsF(f, sigma);
    const raw = f.map((fi) => fi ** sigma);
    const total = raw.reduce((a, b) => a + b, 0);
    expect(w[0]!).toBeCloseTo(raw[0]! / total, 6);
    expect(w[1]!).toBeCloseTo(raw[1]! / total, 6);
    expect(w[2]!).toBeCloseTo(raw[2]! / total, 6);
    expect(w.reduce((s, x) => s + x, 0)).toBeCloseTo(1, 6);
  });

  it("pickingWeightCurve is monotone increasing in f for sigma > 0", () => {
    const curve = pickingWeightCurve(0.8);
    for (let i = 1; i < curve.length; i += 1) {
      expect(curve[i]!.w).toBeGreaterThanOrEqual(curve[i - 1]!.w);
    }
  });
});

describe("renderDemandDist width guard (T-127: 'weird' 1-2 bar bug)", () => {
  // Regression: reading container.clientWidth while a tuning-dock tab's
  // container has just become visible (or hasn't been laid out yet) could
  // report a near-zero-but-nonzero width, producing a degenerate scaleBand
  // with collapsed/garbled bars instead of falling back to a sane default.
  function containerWithWidth(px: number): HTMLElement {
    const el = document.createElement("div");
    Object.defineProperty(el, "clientWidth", { value: px, configurable: true });
    return el;
  }

  it("renders all 7 DOW bars evenly spaced when clientWidth is a small stale value", () => {
    const container = containerWithWidth(8);
    renderDemandDist(
      container,
      { scale_mu: 30, dow_means: [29, 30, 28, 26, 28, 34, 35] },
      null,
      140,
    );
    const bars = Array.from(container.querySelectorAll(".dow-bar"));
    expect(bars).toHaveLength(7);
    const xs = bars.map((b) => Number(b.getAttribute("x")));
    const widths = bars.map((b) => Number(b.getAttribute("width")));
    for (const w of widths) {
      expect(w).toBeGreaterThan(0);
    }
    // Strictly increasing x positions (no collapsed/overlapping bars).
    for (let i = 1; i < xs.length; i += 1) {
      expect(xs[i]!).toBeGreaterThan(xs[i - 1]!);
    }
  });

  it("still renders correctly at a normal clientWidth", () => {
    const container = containerWithWidth(640);
    renderDemandDist(
      container,
      { scale_mu: 30, dow_means: [29, 30, 28, 26, 28, 34, 35] },
      null,
      140,
    );
    expect(container.querySelectorAll(".dow-bar")).toHaveLength(7);
  });

  it("renderPickingVariability produces a finite-width area/line path at a stale small clientWidth", () => {
    const container = containerWithWidth(3);
    renderPickingVariability(container, 0.5);
    const area = container.querySelector(".picking-var-area");
    const line = container.querySelector(".picking-var-line");
    expect(area?.getAttribute("d")).toBeTruthy();
    expect(line?.getAttribute("d")).toBeTruthy();
    expect(area?.getAttribute("d")).not.toMatch(/NaN/);
    expect(line?.getAttribute("d")).not.toMatch(/NaN/);
  });
});

describe("projectedDemandDays", () => {
  it("returns next N days from DOW profile starting at episode day", () => {
    const summary = {
      scale_mu: 30,
      dow_means: [10, 20, 30, 40, 50, 60, 70],
    };
    const rows = projectedDemandDays(0, summary, 3);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toEqual({ day: 0, weekday: "Mon", mean: 10 });
    expect(rows[1]).toEqual({ day: 1, weekday: "Tue", mean: 20 });
    expect(rows[2]).toEqual({ day: 2, weekday: "Wed", mean: 30 });
  });
});

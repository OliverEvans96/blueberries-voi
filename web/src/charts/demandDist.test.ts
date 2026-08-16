/**
 * T-127: picking variability curve + projected demand helpers.
 */
import { describe, expect, it } from "vitest";
import {
  pickingWeightsF,
  pickingWeightCurve,
  projectedDemandDays,
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

import { describe, expect, it } from "vitest";
import {
  BELIEF_HEATMAP_STOPS,
  CHART_PAPER,
  TRUTH_OVERLAY_PALETTE,
  TRUTH_TRAJECTORY_STROKE,
  UNIT_TERMINAL_SOLD,
  UNIT_TERMINAL_SPOILED,
  minHueSeparationDegrees,
  minOklabDistance,
  oklabDistance,
  oklabHueDegrees,
} from "./beliefFreshnessPalette";

describe("beliefFreshnessPalette (OKLab constraints)", () => {
  const overlay = [
    TRUTH_TRAJECTORY_STROKE,
    UNIT_TERMINAL_SOLD,
    UNIT_TERMINAL_SPOILED,
  ] as const;

  it("partitions truth overlay hues away from green heatmap band (~144–165°)", () => {
    const heatHue = oklabHueDegrees(BELIEF_HEATMAP_STOPS[2]!);
    for (const hex of overlay) {
      const d = Math.abs(oklabHueDegrees(hex) - heatHue);
      expect(Math.min(d, 360 - d)).toBeGreaterThanOrEqual(55);
    }
  });

  it("keeps sold and spoiled terminals separable (fixes blue/violet collapse)", () => {
    const dE = oklabDistance(UNIT_TERMINAL_SOLD, UNIT_TERMINAL_SPOILED);
    expect(dE).toBeGreaterThanOrEqual(25);
    const soldHue = oklabHueDegrees(UNIT_TERMINAL_SOLD);
    const spoilHue = oklabHueDegrees(UNIT_TERMINAL_SPOILED);
    const dH = Math.abs(soldHue - spoilHue);
    expect(Math.min(dH, 360 - dH)).toBeGreaterThanOrEqual(90);
  });

  it("maintains minimum pairwise ΔE and Δhue across all truth overlay roles", () => {
    expect(minOklabDistance(overlay)).toBeGreaterThanOrEqual(25);
    expect(minHueSeparationDegrees(overlay)).toBeGreaterThanOrEqual(75);
  });

  it("keeps sold readable on dark heatmap cells", () => {
    expect(oklabDistance(UNIT_TERMINAL_SOLD, BELIEF_HEATMAP_STOPS[2]!)).toBeGreaterThanOrEqual(
      15,
    );
  });

  it("separates sold cyan from secondary histogram truth blue (#2563eb)", () => {
    expect(oklabDistance(UNIT_TERMINAL_SOLD, "#2563eb")).toBeGreaterThanOrEqual(12);
  });

  it("exports stable role map for legend and markers", () => {
    expect(TRUTH_OVERLAY_PALETTE).toEqual({
      alive: TRUTH_TRAJECTORY_STROKE,
      sold: UNIT_TERMINAL_SOLD,
      spoiled: UNIT_TERMINAL_SPOILED,
    });
    expect(oklabDistance(TRUTH_TRAJECTORY_STROKE, CHART_PAPER)).toBeGreaterThanOrEqual(30);
  });
});

/**
 * T-090 / T-127: Observation section (retired Belief nav; charts live in Secondary).
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { STUDIO_SECTIONS } from "./sections";

const HERE = dirname(fileURLToPath(import.meta.url));
const LAYOUT_TS = join(HERE, "react/StudioLayout.tsx");
const LOGIC_TS = join(HERE, "react/studioLogic.ts");
const FRESHNESS_HISTOGRAM_TS = join(HERE, "charts/freshnessHistogram.ts");

describe("Observation section contracts (T-127 shell)", () => {
  it("registers observation with ladder-explainer blurb and no tuning-dock plots", () => {
    const observation = STUDIO_SECTIONS.find((s) => s.id === "observation");
    expect(observation).toBeDefined();
    expect(observation!.plotIds).toEqual([]);
    expect(observation!.blurb.toLowerCase()).toMatch(/observation|knowledge/);
  });

  it("StudioLayout always-on Secondary hosts stacked freshness histogram (T-127)", () => {
    const layout = readFileSync(LAYOUT_TS, "utf8");
    const logic = readFileSync(LOGIC_TS, "utf8");
    expect(logic).toMatch(/renderFreshnessHistogram|freshnessHistogramDataFromFlat/);
    expect(layout).toMatch(/id="chart-belief-age-marginal"/);
    expect(layout).toMatch(/id="chart-belief-lg"/);
  });

  it("ships freshnessHistogram chart module with aggregate bar overlays", () => {
    expect(
      existsSync(FRESHNESS_HISTOGRAM_TS),
      "expected web/src/charts/freshnessHistogram.ts",
    ).toBe(true);
    const histogramSrc = readFileSync(FRESHNESS_HISTOGRAM_TS, "utf8");
    expect(histogramSrc).toMatch(/f_edges|FreshnessHistogramData|renderFreshnessHistogram/);
    expect(histogramSrc).toMatch(/freshness-belief-bar/);
    expect(histogramSrc).toMatch(/freshness-truth-bar/);
  });
});

/**
 * T-148: observation section retired from tuning dock; obs controls in sidebar.
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

describe("Observation section contracts (T-148 v6)", () => {
  it("does not register observation in STUDIO_SECTIONS", () => {
    expect(STUDIO_SECTIONS.find((s) => s.id === "observation")).toBeUndefined();
  });

  it("StudioLayout mounts ObsControlsPane host and belief histogram", () => {
    const layout = readFileSync(LAYOUT_TS, "utf8");
    const logic = readFileSync(LOGIC_TS, "utf8");
    expect(layout).toMatch(/obs-controls-pane-host/);
    expect(logic).toMatch(/ObsControlsPane/);
    expect(logic).toMatch(/renderFreshnessHistogram|freshnessHistogramDataFromFlat/);
    expect(layout).toMatch(/id="chart-belief-lg"/);
  });

  it("ships freshnessHistogram chart module with aggregate bar overlays", () => {
    expect(existsSync(FRESHNESS_HISTOGRAM_TS)).toBe(true);
    const histogramSrc = readFileSync(FRESHNESS_HISTOGRAM_TS, "utf8");
    expect(histogramSrc).toMatch(/renderFreshnessHistogram/);
    expect(histogramSrc).toMatch(/freshness-belief-bar/);
  });
});

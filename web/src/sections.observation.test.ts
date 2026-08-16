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
const BELIEF_AGE_MARGINAL_TS = join(HERE, "charts/beliefAgeMarginal.ts");
const BELIEF_AGE_COUNT_TS = join(HERE, "charts/beliefAgeCount.ts");

describe("Observation section contracts (T-127 shell)", () => {
  it("registers observation with ladder-explainer blurb and no tuning-dock plots", () => {
    const observation = STUDIO_SECTIONS.find((s) => s.id === "observation");
    expect(observation).toBeDefined();
    expect(observation!.plotIds).toEqual([]);
    expect(observation!.blurb.toLowerCase()).toMatch(/observation|knowledge/);
  });

  it("StudioLayout always-on Secondary hosts belief heatmap and age marginal (T-127)", () => {
    const layout = readFileSync(LAYOUT_TS, "utf8");
    const logic = readFileSync(LOGIC_TS, "utf8");
    expect(logic).toMatch(/beliefAgeMarginal|renderBeliefAgeMarginal/);
    expect(layout).toMatch(/id="chart-belief-age-marginal"/);
    expect(layout).toMatch(/id="chart-belief-lg"/);
  });

  it("ships beliefAgeMarginal chart module sharing freshness domain with heatmap", () => {
    expect(
      existsSync(BELIEF_AGE_MARGINAL_TS),
      "expected web/src/charts/beliefAgeMarginal.ts",
    ).toBe(true);
    const marginalSrc = readFileSync(BELIEF_AGE_MARGINAL_TS, "utf8");
    expect(marginalSrc).toMatch(/f_edges|age_marginal|ageMarginal/);
    const heatmapSrc = readFileSync(BELIEF_AGE_COUNT_TS, "utf8");
    expect(heatmapSrc).toMatch(/translate\(\$\{x\(d\.mean_f\)\},\$\{y\(d\.n\)\}\)/);
    expect(heatmapSrc).not.toMatch(/x\(d\.lot_id\)|x\(.*lot.?index/i);
  });
});

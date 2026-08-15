/**
 * T-090 RED: Belief section plotIds + blurb; age-marginal mounts above heatmap.
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

describe("Belief section contracts (T-090)", () => {
  it("plotIds include age-marginal and heatmap plot ids", () => {
    const belief = STUDIO_SECTIONS.find((s) => s.id === "belief");
    expect(belief).toBeDefined();
    const ids = belief!.plotIds;
    expect(ids.length).toBeGreaterThanOrEqual(2);

    const hasMarginal = ids.some((id) =>
      /age[-_]?marginal|marginal/i.test(id),
    );
    const hasHeatmap = ids.some(
      (id) =>
        id === "plot-belief-lg" ||
        /belief.*lg|heatmap|belief-age-count/i.test(id),
    );
    expect(hasMarginal, `expected an age-marginal plotId in ${ids.join(", ")}`).toBe(
      true,
    );
    expect(hasHeatmap, `expected a Belief heatmap plotId in ${ids.join(", ")}`).toBe(
      true,
    );
  });

  it("blurb mentions age×count belief and the age marginal (does not require the word truth)", () => {
    const belief = STUDIO_SECTIONS.find((s) => s.id === "belief");
    expect(belief).toBeDefined();
    const blurb = belief!.blurb.toLowerCase();
    expect(blurb).toMatch(/age\s*[×x]\s*count|age×count/);
    expect(blurb).toMatch(/marginal|age marginal/);
  });

  it("main.ts mounts age-marginal above the Belief heatmap (source order)", () => {
    const layout = readFileSync(LAYOUT_TS, "utf8");
    const logic = readFileSync(LOGIC_TS, "utf8");
    expect(logic).toMatch(/beliefAgeMarginal|renderBeliefAgeMarginal/);

    // data-plot for marginal should appear before heatmap lg in the focus pane markup.
    const marginalIdx = layout.search(
      /data-plot=["'][^"']*(age[-_]?marginal|marginal)[^"']*["']/,
    );
    const heatmapIdx = layout.search(
      /data-plot=["']plot-belief-lg["']|data-plot=["'][^"']*heatmap[^"']*["']/,
    );
    expect(marginalIdx, "expected age-marginal focus-plot in main.ts").toBeGreaterThanOrEqual(
      0,
    );
    expect(heatmapIdx, "expected Belief heatmap focus-plot in main.ts").toBeGreaterThanOrEqual(
      0,
    );
    expect(marginalIdx).toBeLessThan(heatmapIdx);
  });

  it("ships beliefAgeMarginal chart module sharing tau / age domain with heatmap", () => {
    expect(
      existsSync(BELIEF_AGE_MARGINAL_TS),
      "expected web/src/charts/beliefAgeMarginal.ts",
    ).toBe(true);
    const marginalSrc = readFileSync(BELIEF_AGE_MARGINAL_TS, "utf8");
    expect(marginalSrc).toMatch(/tau_edges|age_marginal|ageMarginal/);
    // Heatmap truth markers stay at (lot.tau, lot.n) — no lot-index x.
    const heatmapSrc = readFileSync(BELIEF_AGE_COUNT_TS, "utf8");
    expect(heatmapSrc).toMatch(/translate\(\$\{x\(d\.tau\)\},\$\{y\(d\.n\)\}\)/);
    expect(heatmapSrc).not.toMatch(/x\(d\.lot_id\)|x\(.*lot.?index/i);
  });
});

/**
 * T-124 RED (qa-avail): scenarioAvailability map completeness + ADR 0086 gates.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { STUDIO_SECTIONS } from "./sections";
import type { ScenarioId } from "./types";
import {
  ALL_CONTROL_IDS,
  ALL_PLOT_IDS,
  controlAvailability,
  plotAvailability,
  type Availability,
} from "./scenarioAvailability";

const SCENARIOS: ScenarioId[] = ["P0", "P1", "F1", "F1s", "F2a", "F2"];
const AVAILABILITY_VALUES: Availability[] = ["show", "dim", "unavailable"];

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTROLS_TS = join(HERE, "controls.ts");

/** Canonical studio plot slots (store + run chrome + focus plots + arrival rug). */
function expectedPlotIds(): string[] {
  const fromSections = STUDIO_SECTIONS.flatMap((s) => s.plotIds);
  const store = [
    "store-sales",
    "store-stockout",
    "store-lots",
    "store-spoilage",
  ];
  const run = ["run-pnl-totals", "run-pnl-spark"];
  const extra = ["plot-arrival-prior-rug"];
  return [...new Set([...store, ...run, ...fromSections, ...extra])].sort();
}

/** Slider ids mounted from controls.ts (section knobs). */
function expectedControlIds(): string[] {
  const src = readFileSync(CONTROLS_TS, "utf8");
  const ids = [...src.matchAll(/\bid:\s*"([^"]+)"/g)].map((m) => m[1]!);
  return [...new Set(ids)].sort();
}

describe("T-124 scenarioAvailability map completeness (AC-avail)", () => {
  it("exports every registered plot id for all six ScenarioId rungs", () => {
    const expected = expectedPlotIds();
    expect(ALL_PLOT_IDS.sort()).toEqual(expected);
    for (const plotId of ALL_PLOT_IDS) {
      for (const scenario of SCENARIOS) {
        const value = plotAvailability(plotId, scenario);
        expect(AVAILABILITY_VALUES, `${plotId}@${scenario}`).toContain(value);
      }
    }
  });

  it("exports every section control id for all six ScenarioId rungs", () => {
    const expected = expectedControlIds();
    expect(ALL_CONTROL_IDS.sort()).toEqual(expected);
    for (const controlId of ALL_CONTROL_IDS) {
      for (const scenario of SCENARIOS) {
        const value = controlAvailability(controlId, scenario);
        expect(AVAILABILITY_VALUES, `${controlId}@${scenario}`).toContain(value);
      }
    }
  });
});

describe("T-124 scenarioAvailability ADR 0086 / T-119 gates (AC-avail)", () => {
  it("store-spoilage is unavailable on P0 and show from P1 upward", () => {
    expect(plotAvailability("store-spoilage", "P0")).toBe("unavailable");
    for (const scenario of ["P1", "F1", "F1s", "F2a", "F2"] as const) {
      expect(plotAvailability("store-spoilage", scenario)).toBe("show");
    }
  });

  it("plot-arrival-prior-rug follows pack_date_per_lot delivery channel", () => {
    for (const scenario of ["P0", "P1", "F1", "F1s"] as const) {
      expect(plotAvailability("plot-arrival-prior-rug", scenario)).toBe(
        "unavailable",
      );
    }
    for (const scenario of ["F2a", "F2"] as const) {
      expect(plotAvailability("plot-arrival-prior-rug", scenario)).toBe("show");
    }
  });


});

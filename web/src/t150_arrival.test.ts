/**
 * T-150 — web Phase 1 terminology + Phase 3 arrival frontend (RED).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const WEB_SRC = fileURLToPath(new URL(".", import.meta.url));

function read(rel: string): string {
  return readFileSync(join(WEB_SRC, rel), "utf8");
}

function walkTs(dir: string): string[] {
  const out: string[] = [];
  for (const ent of readdirSync(dir)) {
    const p = join(dir, ent);
    if (statSync(p).isDirectory()) {
      if (ent === "node_modules" || ent === "dist-lib") continue;
      out.push(...walkTs(p));
    } else if (ent.endsWith(".ts") || ent.endsWith(".tsx")) {
      out.push(p);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Phase 1 — AC1.4, AC1.5
// ---------------------------------------------------------------------------

describe("T-150 Phase 1 terminology", () => {
  it("AC1.5: StoreChartTabs tab label has no age framing", () => {
    const src = read("react/StoreChartTabs.tsx");
    expect(src).not.toMatch(/Age & spoilage/);
    expect(src).toMatch(/freshness/i);
  });

  it("AC1.5: projector axis label already excludes age (extend to tab)", () => {
    const testSrc = read("engine/projector.test.ts");
    expect(testSrc).toMatch(/not\.toContain\("age"\)/i);
    const tabsTest = read("react/StoreChartTabs.test.ts");
    expect(tabsTest).toMatch(/not\.toContain\("age"\)|Freshness/i);
  });

  it("AC1.4: freshness CSS class renames in stylesheets", () => {
    const css = read("styles.css");
    expect(css).not.toMatch(/\.age-young/);
    expect(css).not.toMatch(/\.age-mid/);
    expect(css).not.toMatch(/\.age-old/);
    expect(css).toMatch(/\.freshness-young/);
    expect(css).toMatch(/\.freshness-mid/);
    expect(css).toMatch(/\.freshness-old/);
  });
});

// ---------------------------------------------------------------------------
// Phase 3 — AC3.2, AC3.4, AC3.5
// ---------------------------------------------------------------------------

describe("T-150 Phase 3 arrival frontend", () => {
  const MOCK_FORBIDDEN = [
    "ABDELLA_AGES_BASE",
    "baseMixAges",
    "sampleArrivalAge",
    "arrivalAgePriorPdf",
    "arrivalFreshnessPriorPdf",
    "transitAgeFactor",
    "ageToF",
    "meanShrink",
  ] as const;

  it("AC3.4: mock arrival PDF helpers deleted from generate.ts", () => {
    const src = read("mock/generate.ts");
    for (const sym of MOCK_FORBIDDEN) {
      expect(src, `RED: delete ${sym} from mock/generate.ts`).not.toContain(sym);
    }
    expect(src).toMatch(/ageAndSpoilUnits|freshnessAndSpoilUnits/);
  });

  it("AC3.4: no TypeScript arrival PDF outside engine adapter", () => {
    const files = walkTs(WEB_SRC).filter(
      (p) =>
        !p.includes("mock/generate.ts") &&
        !p.includes("t150_arrival.test.ts") &&
        !p.includes(".test."),
    );
    const offenders: string[] = [];
    for (const file of files) {
      const rel = relative(WEB_SRC, file);
      const src = readFileSync(file, "utf8");
      if (
        /arrivalFreshnessPriorPdf|arrivalAgePriorPdf|sampleArrivalAge/.test(src)
      ) {
        offenders.push(rel);
      }
    }
    expect(offenders, "RED: arrival PDF only via engine adapter").toEqual([]);
  });

  it("AC3.4: arrivalPrior.ts renders engine-supplied values only", () => {
    const src = read("charts/arrivalPrior.ts");
    expect(src).not.toMatch(/from ["'].*mock\/generate/);
    expect(src).toMatch(/arrival_summary|snapshot/i);
    expect(src).toMatch(/f_at_receipt|rug/i);
  });

  it("AC3.2: dead studio knobs wired or removed", () => {
    const types = read("types.ts");
    const controls = read("controls.ts");
    for (const knob of [
      "break_rho",
      "sensor_sigma",
      "transit_temp_bias_c",
    ] as const) {
      const inTypes = types.includes(knob);
      const inControls = controls.includes(knob);
      if (inTypes || inControls) {
        const session = readFileSync(
          join(WEB_SRC, "../../crates/voi_core/src/session.rs"),
          "utf8",
        );
        expect(
          session.includes(knob) || session.includes(knob.replace(/_/g, "")),
          `RED: studio knob ${knob} must be wired in session.rs or removed from web`,
        ).toBe(true);
      }
    }
  });

  it("AC3.5: live_lots wire carries within-lot spread beyond mean_f", () => {
    const engineTypes = read("engine/types.ts");
    expect(engineTypes).toMatch(/live_lots/);
    expect(engineTypes).toMatch(/f_spread|unit_f|freshness_spread|f_values/i);
    const projector = read("engine/projector.ts");
    expect(projector).toMatch(/live_lots/);
    expect(projector).toMatch(/f_spread|unit_f|freshness_spread|f_values/i);
  });
});

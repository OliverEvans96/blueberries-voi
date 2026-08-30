/**
 * T-087 RED: Demand UI — DOW profile + protection coverage (CAL-C3).
 *
 * Demand section must show calendar structure from Snapshot demand_summary +
 * schedule (seven-day DOW series; Sun/Tue/Thu protection 3/3/4), not a
 * stationary μ-only PMF or unmarked decorative sinusoid presented as physics.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { DemandSummary, ScheduleWire, Snapshot } from "../engine/types";
import { MockAdapter } from "../mock/adapter";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(HERE, "../..");
const REPO_ROOT = join(WEB_ROOT, "..");
const MAIN_TS = join(WEB_ROOT, "src/react/studioLogic.ts");
const DEMAND_DIST_TS = join(HERE, "demandDist.ts");
const SALES_DEMAND_TS = join(HERE, "salesDemand.ts");
const GENERATE_TS = join(WEB_ROOT, "src/mock/generate.ts");
const SECTIONS_TS = join(WEB_ROOT, "src/sections.ts");
const PACKAGE_JSON = join(WEB_ROOT, "package.json");
const PYPROJECT = join(REPO_ROOT, "pyproject.toml");

/** Chart modules that may own DOW / protection UI (spec: demandDist or successor). */
const DEMAND_UI_CANDIDATES = [
  DEMAND_DIST_TS,
  join(HERE, "demandProfile.ts"),
  join(HERE, "dowProfile.ts"),
  join(HERE, "protectionCoverage.ts"),
];

const DEFAULT_SCHEDULE: ScheduleWire = {
  delivery_weekdays: [0, 2, 4],
  order_weekdays: [6, 1, 3],
  lead_time_days: 1,
  epoch: "2024-01-01",
};

const MOCK_SUMMARY: DemandSummary = {
  scale_mu: 30,
  dow_means: [29.1, 30.3, 27.9, 25.8, 27.8, 33.9, 35.3],
};

const WEEKDAY_NAME: Record<number, string> = {
  0: "Mon",
  1: "Tue",
  2: "Wed",
  3: "Thu",
  4: "Fri",
  5: "Sat",
  6: "Sun",
};

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

function demandUiSources(): string[] {
  return DEMAND_UI_CANDIDATES.filter((p) => existsSync(p)).map((p) =>
    readFileSync(p, "utf8"),
  );
}

function combinedDemandUiSrc(): string {
  return demandUiSources().join("\n");
}

function demandSummaryFromSnapshot(
  snap: Snapshot,
): Record<string, unknown> | null {
  const top = (snap as Record<string, unknown>).demand_summary;
  if (top && typeof top === "object" && !Array.isArray(top)) {
    return top as Record<string, unknown>;
  }
  return null;
}

function looksMarkedNonPhysics(src: string): boolean {
  return /non[-_]?physics|mock[-_]?only|not\s+physics|decorative|teaching\s+stub|unrelated\s+to\s+physics/i.test(
    src,
  );
}

describe("T-087 DOW profile from demand_summary", () => {
  it("demand chart module exposes a length-7 DOW series from DemandSummary", async () => {
    const mod = (await import("./demandDist")) as Record<string, unknown>;
    const successorPaths = [
      "./demandProfile",
      "./dowProfile",
      "./protectionCoverage",
    ];
    let builder: ((s: DemandSummary) => number[]) | undefined;
    for (const key of [
      "dowSeriesFromDemandSummary",
      "dowMeansFromSummary",
      "dowProfileSeries",
    ]) {
      if (typeof mod[key] === "function") {
        builder = mod[key] as (s: DemandSummary) => number[];
        break;
      }
    }
    if (!builder) {
      for (const rel of successorPaths) {
        try {
          const m = (await import(rel)) as Record<string, unknown>;
          for (const key of [
            "dowSeriesFromDemandSummary",
            "dowMeansFromSummary",
            "dowProfileSeries",
          ]) {
            if (typeof m[key] === "function") {
              builder = m[key] as (s: DemandSummary) => number[];
              break;
            }
          }
        } catch {
          /* successor not present yet */
        }
        if (builder) break;
      }
    }
    expect(
      builder,
      "expected dowSeriesFromDemandSummary (or alias) on demandDist / successor",
    ).toBeTypeOf("function");
    const series = builder!(MOCK_SUMMARY);
    expect(series).toHaveLength(7);
    expect(series).toEqual(MOCK_SUMMARY.dow_means);
  });

  it("demandDist (or successor) reads demand_summary / dow_means — not μ-only demandPmf alone", () => {
    const src = combinedDemandUiSrc();
    expect(src.length).toBeGreaterThan(0);
    const code = stripComments(src);
    expect(
      /demand_summary|dow_means|dow_factors/.test(code),
      "Demand UI must consume Snapshot demand_summary (dow_means / dow_factors)",
    ).toBe(true);
    // Stationary μ-only PMF as the sole Demand-section physics is disallowed unless
    // clearly marked non-physics (covered in a sibling test).
    const stillMuOnly =
      /demandPmf\s*\(/.test(code) &&
      !/demand_summary|dow_means|dow_factors/.test(code);
    expect(stillMuOnly).toBe(false);
  });

  it("react/studioLogic.ts wires demand forecast chart with episode history", () => {
    const main = stripComments(readFileSync(MAIN_TS, "utf8"));
    expect(main).toMatch(/renderDemandForecast/);
    expect(main).toMatch(/vm\.history/);
  });

  it("react/studioLogic.ts colocates demand forecast chart when demand section is active", () => {
    const main = stripComments(readFileSync(MAIN_TS, "utf8"));
    expect(main).not.toMatch(/chart-demand-host/);
    expect(main).toMatch(/renderDemandForecast/);
    expect(main).toMatch(/plot-demand-forecast/);
  });

  it("react/studioLogic.ts keeps mountTuningChartHosts for section changes", () => {
    const main = stripComments(readFileSync(MAIN_TS, "utf8"));
    expect(main).toMatch(/mountTuningChartHosts/);
  });
});

describe("T-087 protection-interval coverage 3/3/4", () => {
  it("exports protection coverage for order days Sun/Tue/Thu as 3/3/4", async () => {
    const mod = (await import("./demandDist")) as Record<string, unknown>;
    let coverage:
      | ((s: ScheduleWire) => Array<{
          order_weekday: number;
          demand_days: number;
          label?: string;
        }>)
      | undefined;
    for (const key of [
      "protectionCoverageFromSchedule",
      "protectionSpansFromSchedule",
      "orderDayProtectionCoverage",
    ]) {
      if (typeof mod[key] === "function") {
        coverage = mod[key] as typeof coverage;
        break;
      }
    }
    if (!coverage) {
      for (const rel of [
        "./demandProfile",
        "./dowProfile",
        "./protectionCoverage",
      ]) {
        try {
          const m = (await import(rel)) as Record<string, unknown>;
          for (const key of [
            "protectionCoverageFromSchedule",
            "protectionSpansFromSchedule",
            "orderDayProtectionCoverage",
          ]) {
            if (typeof m[key] === "function") {
              coverage = m[key] as typeof coverage;
              break;
            }
          }
        } catch {
          /* not yet */
        }
        if (coverage) break;
      }
    }
    expect(
      coverage,
      "expected protectionCoverageFromSchedule (or alias) for Demand UI labels",
    ).toBeTypeOf("function");
    const rows = coverage!(DEFAULT_SCHEDULE);
    const byWd = new Map(rows.map((r) => [r.order_weekday, r.demand_days]));
    expect(byWd.get(6), "Sun protection demand-days").toBe(3);
    expect(byWd.get(1), "Tue protection demand-days").toBe(3);
    expect(byWd.get(3), "Thu protection demand-days").toBe(4);
  });

  it("Demand UI source may still expose protection coverage helpers for schedule math", () => {
    const chartSrc = combinedDemandUiSrc();
    const blob = chartSrc;
    expect(/protectionCoverageFromSchedule/.test(blob)).toBe(true);
  });
});

describe("T-087 no unmarked decorative sinusoid / μ-only as physics", () => {
  it("mock generate.ts Math.sin seasonal factor is absent or marked non-physics", () => {
    const src = readFileSync(GENERATE_TS, "utf8");
    const hasSin = /Math\.sin\s*\(/.test(src);
    if (!hasSin) {
      expect(hasSin).toBe(false);
      return;
    }
    // Decorative sinusoid remains only if clearly marked non-physics near use.
    const sinIdx = src.search(/Math\.sin\s*\(/);
    const window = src.slice(Math.max(0, sinIdx - 280), sinIdx + 200);
    expect(
      looksMarkedNonPhysics(window),
      "Math.sin demand seasonality must be removed or marked non-physics (not presented as physics)",
    ).toBe(true);
  });

  it("μ-only demandDist PMF is replaced by DOW profile or marked non-physics", () => {
    const dist = readFileSync(DEMAND_DIST_TS, "utf8");
    const usesPmf = /demandPmf\s*\(/.test(stripComments(dist));
    const usesDow = /demand_summary|dow_means|dow_factors/.test(
      stripComments(dist),
    );
    if (usesDow && !usesPmf) {
      expect(usesDow).toBe(true);
      return;
    }
    if (usesPmf) {
      expect(
        looksMarkedNonPhysics(dist),
        "i.i.d. μ-only demandPmf chart must be updated to DOW or marked non-physics",
      ).toBe(true);
    }
    // Prefer DOW path for the Demand section.
    expect(
      usesDow,
      "Demand chart should render DOW profile from demand_summary",
    ).toBe(true);
  });

  it("salesDemand chart is DOW-aware, history-only, or marked non-physics", () => {
    const src = readFileSync(SALES_DEMAND_TS, "utf8");
    const code = stripComments(src);
    // History of realized sales/demand is fine; forbid inventing a μ-only sinusoid here.
    expect(code).not.toMatch(/Math\.sin\s*\(/);
    const inventsIidMu =
      /demand_mu/.test(code) && !looksMarkedNonPhysics(src);
    expect(
      inventsIidMu,
      "salesDemand must not invent unmarked i.i.d. μ-only demand curves",
    ).toBe(false);
  });
});

describe("T-087 MockAdapter stub profile data for charts", () => {
  it("init Snapshot demand_summary has scale_mu and length-7 dow_means", async () => {
    const adapter = new MockAdapter(42);
    const snap = await adapter.init({});
    const summary = demandSummaryFromSnapshot(snap);
    expect(summary, "MockAdapter Snapshot.demand_summary").not.toBeNull();
    const scale = summary!.scale_mu ?? summary!.scale_target_mu;
    expect(typeof scale).toBe("number");
    expect(Number(scale)).toBeGreaterThan(0);
    const dow = (summary!.dow_means ?? summary!.dow_factors) as number[];
    expect(Array.isArray(dow)).toBe(true);
    expect(dow).toHaveLength(7);
    for (const x of dow) {
      expect(typeof x).toBe("number");
      expect(x).toBeGreaterThan(0);
    }
  });

  it("init Snapshot schedule order_weekdays are Sun/Tue/Thu for protection UI", async () => {
    const adapter = new MockAdapter(42);
    const snap = await adapter.init({});
    const schedule = snap.schedule;
    expect(schedule, "MockAdapter Snapshot.schedule").toBeTruthy();
    expect(new Set(schedule!.order_weekdays)).toEqual(new Set([6, 1, 3]));
    expect(schedule!.lead_time_days).toBe(1);
  });
});

describe("T-087 smoke: DOW length 7 + protection labels", () => {
  it("contract: DOW series length is 7 and protection map is 3/3/4 for default order days", async () => {
    // Smoke checklist encoded as assertions (spec allows unit/smoke).
    const adapter = new MockAdapter(7);
    const snap = await adapter.init({});
    const summary = demandSummaryFromSnapshot(snap)!;
    const dow = (summary.dow_means ?? summary.dow_factors) as number[];
    expect(dow).toHaveLength(7);

    const mod = (await import("./demandDist")) as Record<string, unknown>;
    let coverage:
      | ((s: ScheduleWire) => Array<{
          order_weekday: number;
          demand_days: number;
        }>)
      | undefined;
    for (const key of [
      "protectionCoverageFromSchedule",
      "protectionSpansFromSchedule",
      "orderDayProtectionCoverage",
    ]) {
      if (typeof mod[key] === "function") {
        coverage = mod[key] as typeof coverage;
        break;
      }
    }
    expect(
      coverage,
      "smoke requires protectionCoverageFromSchedule so UI can label 3/3/4",
    ).toBeTypeOf("function");
    const rows = coverage!(snap.schedule ?? DEFAULT_SCHEDULE);
    const expected: Record<number, number> = { 6: 3, 1: 3, 3: 4 };
    for (const [wd, days] of Object.entries(expected)) {
      const row = rows.find((r) => r.order_weekday === Number(wd));
      expect(
        row,
        `protection label for ${WEEKDAY_NAME[Number(wd)] ?? wd}`,
      ).toBeTruthy();
      expect(row!.demand_days).toBe(days);
    }
  });
});

describe("T-087 no HF in browser path / no new runtime Python deps", () => {
  it("web package.json dependencies do not include huggingface / transformers / datasets", () => {
    const pkg = JSON.parse(readFileSync(PACKAGE_JSON, "utf8")) as {
      dependencies?: Record<string, string>;
      devDependencies?: Record<string, string>;
    };
    const names = [
      ...Object.keys(pkg.dependencies ?? {}),
      ...Object.keys(pkg.devDependencies ?? {}),
    ];
    for (const n of names) {
      expect(n).not.toMatch(/huggingface|transformers|^datasets$/i);
    }
  });

  it("web/src does not import Hugging Face datasets in the browser path", () => {
    const roots = [
      join(WEB_ROOT, "src/react/studioLogic.ts"),
      join(WEB_ROOT, "src/charts"),
      join(WEB_ROOT, "src/engine"),
      join(WEB_ROOT, "src/mock"),
    ];
    const files: string[] = [];
    for (const root of roots) {
      if (!existsSync(root)) continue;
      if (root.endsWith(".ts")) {
        files.push(root);
        continue;
      }
      // shallow: chart/engine/mock *.ts only
      for (const name of readdirSync(root)) {
        const p = join(root, name);
        if (statSync(p).isFile() && name.endsWith(".ts")) files.push(p);
      }
    }
    for (const file of files) {
      const src = readFileSync(file, "utf8");
      expect(src, file).not.toMatch(
        /from\s+["']@huggingface|from\s+["']transformers|huggingface\.co|Dingdong-Inc\/FreshRetailNet/i,
      );
    }
  });

  it("pyproject core runtime deps stay free of datasets / HF (freshnet extra only)", () => {
    const toml = readFileSync(PYPROJECT, "utf8");
    // Core [project] dependencies block before optional-dependencies.
    const coreMatch = toml.match(
      /dependencies\s*=\s*\[([\s\S]*?)\]\s*\n\s*\[project\.optional-dependencies\]/,
    );
    expect(coreMatch, "expected core dependencies list").toBeTruthy();
    const core = coreMatch![1]!;
    expect(core).not.toMatch(/datasets|transformers|huggingface/i);
    expect(toml).toMatch(/\[project\.optional-dependencies\]/);
  });
});

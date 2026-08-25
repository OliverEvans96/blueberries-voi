/**
 * Guard: retired belief/truth hex must not reappear in chart sources.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const RETIRED = ["#e6b800", "#2563eb", "#8a2f1f"] as const;

const CHART_PATHS = [
  "beliefFreshnessPalette.ts",
  "freshnessHistogram.ts",
  "beliefFreshnessTime.ts",
] as const;

describe("belief/truth color guard", () => {
  for (const file of CHART_PATHS) {
    it(`${file} does not use retired belief/truth hex`, () => {
      const src = readFileSync(join(__dirname, file), "utf8").toLowerCase();
      for (const hex of RETIRED) {
        expect(src, `${file} must not contain ${hex}`).not.toContain(hex);
      }
    });
  }
});

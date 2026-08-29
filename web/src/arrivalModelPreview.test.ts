import { describe, expect, it } from "vitest";
import {
  durationPmfForProduct,
  expectedDurationDays,
  lambdaClean,
  phiSetFromLegs,
  poissonPmf,
} from "./arrivalModelPreview";

describe("arrivalModelPreview", () => {
  it("duration pmf sums to ~1 for abdella_all", () => {
    const pmf = durationPmfForProduct("abdella_all");
    const total = [2, 3, 4, 5, 6, 7].reduce((s, k) => s + (pmf[k] ?? 0), 0);
    expect(total).toBeCloseTo(1, 2);
  });

  it("abdella_mix mean duration lies between short and long haul", () => {
    const mix = expectedDurationDays("abdella_mix");
    const short = expectedDurationDays("short_haul");
    const long = expectedDurationDays("long_haul");
    expect(mix).toBeGreaterThan(short);
    expect(mix).toBeLessThan(long);
  });

  it("lambda_clean scales linearly with d at fixed phi_set", () => {
    const phi = phiSetFromLegs(0);
    expect(lambdaClean(5, phi) * 2).toBeCloseTo(lambdaClean(10, phi), 6);
  });

  it("poisson pmf sums to ~1", () => {
    const pmf = poissonPmf(0.44, 4);
    expect(pmf.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 4);
  });
});

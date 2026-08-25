/**
 * damped_sw demo chart — protection quantile + coverage bias monotonicity.
 */
import { describe, expect, it } from "vitest";
import {
  caseRound,
  computeDampedSwDecomposition,
  coverageBiasScore,
  homogeneousProtectionQuantile,
  protectionDemandQuantile,
} from "./dampedSwDemo";

describe("protectionDemandQuantile", () => {
  it("is monotone increasing in alpha for homogeneous demand", () => {
    const mus = [30, 30, 30];
    const qLow = protectionDemandQuantile(0.6, 2.5, 3, mus);
    const qMid = protectionDemandQuantile(0.8, 2.5, 3, mus);
    const qHigh = protectionDemandQuantile(0.95, 2.5, 3, mus);
    expect(qMid).toBeGreaterThanOrEqual(qLow);
    expect(qHigh).toBeGreaterThanOrEqual(qMid);
  });

  it("homogeneous path matches closed-form helper", () => {
    const mu = 28;
    const vm = 2.2;
    const n = 4;
    const alpha = 0.9;
    const fromHelper = homogeneousProtectionQuantile(alpha, mu, vm, n);
    const fromRouter = protectionDemandQuantile(alpha, vm, n, [mu, mu, mu, mu]);
    expect(fromRouter).toBeCloseTo(fromHelper, 6);
  });

  it("heterogeneous DOW convolution is at least the min-day quantile", () => {
    const flat = protectionDemandQuantile(0.9, 2.5, 3, [30, 30, 30]);
    const het = protectionDemandQuantile(0.9, 2.5, 3, [20, 30, 40]);
    expect(het).toBeGreaterThan(flat * 0.8);
  });
});

describe("coverageBiasScore", () => {
  it("increases with alpha holding rho fixed", () => {
    const low = coverageBiasScore(0.55, 0.8);
    const high = coverageBiasScore(0.95, 0.8);
    expect(high).toBeGreaterThan(low);
  });

  it("increases with rho holding alpha fixed", () => {
    const low = coverageBiasScore(0.9, 0.2);
    const high = coverageBiasScore(0.9, 0.95);
    expect(high).toBeGreaterThan(low);
  });

  it("clamps to [0, 1]", () => {
    expect(coverageBiasScore(0.5, 0.1)).toBeGreaterThanOrEqual(0);
    expect(coverageBiasScore(0.99, 1)).toBeLessThanOrEqual(1);
  });
});

describe("caseRound", () => {
  it("snaps to case multiples", () => {
    expect(caseRound(10, 8)).toBe(8);
    expect(caseRound(12, 8)).toBe(16);
    expect(caseRound(0, 8)).toBe(0);
  });
});

describe("computeDampedSwDecomposition", () => {
  it("order qty is case-rounded rho times gap", () => {
    const decomp = computeDampedSwDecomposition({
      alpha: 0.9,
      rho: 0.8,
      caseSize: 8,
      demandVm: 2.5,
      demandSummary: { scale_mu: 30, dow_means: [30, 30, 30, 30, 30, 30, 30] },
      schedule: null,
      episodeDay: 0,
      effectiveInventory: 20,
    });
    expect(decomp.gap).toBeCloseTo(
      Math.max(0, decomp.targetQuantile - decomp.effectiveInventory),
      6,
    );
    expect(decomp.orderQty).toBe(
      caseRound(decomp.gap * 0.8, 8),
    );
  });
});

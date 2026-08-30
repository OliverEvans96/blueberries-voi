/**
 * damped_sw demo chart — protection quantile + coverage bias monotonicity.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import {
  caseRound,
  computeDampedSwDecomposition,
  coverageBiasScore,
  homogeneousProtectionQuantile,
  protectionDemandPmf,
  protectionDemandQuantile,
  renderDampedSwDemo,
} from "./dampedSwDemo";

function quantileFromPmf(pmf: { k: number; p: number }[], q: number): number {
  let cum = 0;
  for (const row of pmf) {
    cum += row.p;
    if (cum >= q) return row.k;
  }
  return pmf[pmf.length - 1]?.k ?? 0;
}

function chartHost(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 420 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("protectionDemandPmf", () => {
  it("pmf masses sum to approximately 1", () => {
    const pmf = protectionDemandPmf(2.5, 3, [30, 30, 30]);
    const total = pmf.reduce((sum, row) => sum + row.p, 0);
    expect(total).toBeCloseTo(1, 6);
  });

  it("quantileFromPmf is consistent with protectionDemandQuantile", () => {
    const mus = [28, 32, 30];
    const vm = 2.2;
    const days = 3;
    for (const alpha of [0.7, 0.9, 0.95]) {
      const pmf = protectionDemandPmf(vm, days, mus);
      expect(quantileFromPmf(pmf, alpha)).toBe(
        protectionDemandQuantile(alpha, vm, days, mus),
      );
    }
  });
});

describe("renderDampedSwDemo", () => {
  it("draws histogram bars, two vertical markers, and legend entries", () => {
    const host = chartHost();
    renderDampedSwDemo(host, {
      alpha: 0.9,
      rho: 0.8,
      policy: "damped_sw",
      caseSize: 8,
      demandVm: 2.5,
      demandSummary: { scale_mu: 30, dow_means: [30, 30, 30, 30, 30, 30, 30] },
      schedule: null,
      episodeDay: 0,
      effectiveInventory: 20,
    });

    const svg = host.querySelector("svg.damped-sw-demo");
    expect(svg).not.toBeNull();
    expect(host.querySelectorAll(".prot-demand-hist-bar").length).toBeGreaterThan(0);
    expect(host.querySelectorAll(".damped-sw-marker").length).toBe(2);
    expect(host.querySelector(".damped-sw-marker--target")).not.toBeNull();
    expect(host.querySelector(".damped-sw-marker--order")).not.toBeNull();
    expect(host.querySelector(".damped-sw-legend")).not.toBeNull();
    expect(host.querySelectorAll(".legend-label").length).toBe(2);
  });

  it("shows constant-policy hint instead of histogram", () => {
    const host = chartHost();
    renderDampedSwDemo(host, {
      alpha: 0.9,
      rho: 0.8,
      policy: "constant",
      caseSize: 8,
      demandVm: 2.5,
      demandSummary: null,
      schedule: null,
      episodeDay: 0,
      effectiveInventory: 20,
    });
    expect(host.querySelector(".damped-sw-demo-hint")).not.toBeNull();
    expect(host.querySelectorAll(".prot-demand-hist-bar").length).toBe(0);
  });
});

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
    const low = coverageBiasScore(0.9, 0.5);
    const high = coverageBiasScore(0.9, 1.5);
    expect(high).toBeGreaterThan(low);
  });

  it("clamps to [0, 1]", () => {
    expect(coverageBiasScore(0.5, 0.5)).toBeGreaterThanOrEqual(0);
    expect(coverageBiasScore(0.99, 2.0)).toBeLessThanOrEqual(1);
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

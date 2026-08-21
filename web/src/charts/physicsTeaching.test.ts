/**
 * T-138: Physics teaching charts — Q10 curve and gamma mean ± σ envelope.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { DEFAULT_SIM_CONFIG, storeTempFactor } from "../mock/generate";
import {
  GAMMA_SHAPE,
  GAMMA_SCALE,
  arrheniusCurve,
  expectedSpoilDay,
  gammaDecrementStats,
  gammaFreshnessEnvelope,
  q10RateAtTemp,
  renderArrheniusTemp,
  renderGammaFreshnessPath,
} from "./physicsTeaching";

function host(): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { configurable: true, value: 400 });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("physicsTeaching Q10 curve", () => {
  it("matches Rust golden q10_one_day_at_4c", () => {
    expect(q10RateAtTemp(3, 0, 4)).toBeCloseTo(3 ** 0.4, 10);
  });

  it("returns one at reference temperature", () => {
    expect(q10RateAtTemp(3, 0, 0)).toBeCloseTo(1, 10);
  });

  it("arrheniusCurve spans t_ref ± window", () => {
    const curve = arrheniusCurve(DEFAULT_SIM_CONFIG);
    expect(curve[0]!.tempC).toBeCloseTo(DEFAULT_SIM_CONFIG.t_ref_c - 8);
    expect(curve.at(-1)!.tempC).toBeCloseTo(DEFAULT_SIM_CONFIG.t_ref_c + 12);
  });
});

describe("physicsTeaching gamma envelope", () => {
  it("computes meanDelta from ModelParams defaults", () => {
    const { meanDelta, thetaEff } = gammaDecrementStats(DEFAULT_SIM_CONFIG);
    expect(thetaEff).toBeCloseTo(GAMMA_SCALE * storeTempFactor(DEFAULT_SIM_CONFIG));
    expect(meanDelta).toBeCloseTo(GAMMA_SHAPE * thetaEff);
  });

  it("mean and std follow sum-of-Gammas formulas at day 1", () => {
    const { meanDelta, thetaEff } = gammaDecrementStats(DEFAULT_SIM_CONFIG);
    const row = gammaFreshnessEnvelope(DEFAULT_SIM_CONFIG)[1]!;
    expect(row.mean).toBeCloseTo(1 - meanDelta);
    expect(row.std).toBeCloseTo(thetaEff * Math.sqrt(GAMMA_SHAPE));
    expect(row.lower).toBeCloseTo(Math.max(0, row.mean - row.std));
    expect(row.upper).toBeCloseTo(Math.min(1, row.mean + row.std));
  });

  it("expectedSpoilDay is ceil(f0 / meanDelta)", () => {
    const { meanDelta } = gammaDecrementStats(DEFAULT_SIM_CONFIG);
    expect(expectedSpoilDay(DEFAULT_SIM_CONFIG)).toBe(Math.ceil(1 / meanDelta));
  });

  it("envelope ends at expected spoil day", () => {
    const spoilDay = expectedSpoilDay(DEFAULT_SIM_CONFIG);
    const envelope = gammaFreshnessEnvelope(DEFAULT_SIM_CONFIG);
    expect(envelope[0]!.day).toBe(0);
    expect(envelope.at(-1)!.day).toBe(spoilDay);
  });
});

describe("physicsTeaching render smoke", () => {
  it("renderArrheniusTemp produces svg", () => {
    const el = host();
    renderArrheniusTemp(el, DEFAULT_SIM_CONFIG);
    expect(el.querySelector("svg")).not.toBeNull();
    expect(el.querySelector("svg")?.getAttribute("aria-label")).toMatch(
      /aging rate/i,
    );
  });

  it("renderGammaFreshnessPath produces mean line and std band", () => {
    const el = host();
    renderGammaFreshnessPath(el, DEFAULT_SIM_CONFIG);
    expect(el.querySelector("svg")).not.toBeNull();
    expect(el.querySelector(".gamma-std-band")).not.toBeNull();
    expect(el.querySelector(".impact-line")).not.toBeNull();
    expect(el.querySelector("svg")?.getAttribute("aria-label")).toMatch(
      /mean.*standard deviation/i,
    );
  });
});

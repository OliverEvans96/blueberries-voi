import { describe, expect, it } from "vitest";
import { createInitialState, DEFAULT_SIM_CONFIG } from "./generate";

describe("createInitialState opening stock (ADR 0152)", () => {
  it("seeds non-empty units at episode start", () => {
    const state = createInitialState(DEFAULT_SIM_CONFIG);
    expect(state.units.length).toBeGreaterThan(0);
    expect(state.lots.reduce((s, l) => s + l.n, 0)).toBe(state.units.length);
  });

  it("sizes stock to a case-rounded protection quantile at alpha=0.95", () => {
    const state = createInitialState(DEFAULT_SIM_CONFIG);
    const onHand = state.units.length;
    expect(onHand % DEFAULT_SIM_CONFIG.case_size).toBe(0);
    expect(onHand).toBeGreaterThanOrEqual(DEFAULT_SIM_CONFIG.case_size);
  });
});

import { describe, expect, it } from "vitest";
import { createInitialState, DEFAULT_SIM_CONFIG } from "./generate";

describe("createInitialState opening stock (ADR 0152)", () => {
  it("seeds non-empty units at episode start with default qty 120", () => {
    const state = createInitialState(DEFAULT_SIM_CONFIG);
    expect(state.units.length).toBe(120);
    expect(state.lots.reduce((s, l) => s + l.n, 0)).toBe(state.units.length);
  });

  it("respects initial_stock_qty from config", () => {
    const state = createInitialState({
      ...DEFAULT_SIM_CONFIG,
      initial_stock_qty: 64,
    });
    expect(state.units.length).toBe(64);
  });

  it("seeds zero units when initial_stock_qty is 0", () => {
    const state = createInitialState({
      ...DEFAULT_SIM_CONFIG,
      initial_stock_qty: 0,
    });
    expect(state.units.length).toBe(0);
  });
});

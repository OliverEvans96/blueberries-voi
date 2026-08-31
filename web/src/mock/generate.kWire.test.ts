import { describe, expect, it } from "vitest";
import { DEFAULT_K_WIRE, generateFlatBelief } from "./generate";

describe("DEFAULT_K_WIRE", () => {
  it("matches production belief wire resolution", () => {
    expect(DEFAULT_K_WIRE).toBe(30);
  });

  it("generateFlatBelief uses DEFAULT_K_WIRE when K omitted", () => {
    const belief = generateFlatBelief(
      [{ lot_id: 1, n: 4, mean_f: 0.5, f_values: [0.5, 0.5, 0.5, 0.5] }],
      () => 0.5,
    );
    expect(belief.K).toBe(30);
    expect(belief.f_grid).toHaveLength(30);
  });
});

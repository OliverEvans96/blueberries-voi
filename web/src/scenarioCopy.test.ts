import { describe, expect, it } from "vitest";
import { scenarioDescription, scenarioTitle } from "./scenarioCopy";

describe("scenarioTitle / scenarioDescription", () => {
  it("returns locked copy for ladder ids", () => {
    expect(scenarioTitle("P1")).toBe("Shrink gun");
    expect(scenarioTitle("F2a")).toBe("Pack date on ASN");
    expect(scenarioDescription("F2a")).toMatch(/arrival-age prior/i);
  });

  it("returns custom label for WASM custom obs_scenario", () => {
    expect(scenarioTitle("custom")).toBe("Custom channels");
    expect(scenarioDescription("custom")).toMatch(/named preset/i);
  });

  it("does not throw for unknown ids", () => {
    expect(scenarioTitle("bogus")).toBe("Unknown scenario");
    expect(scenarioDescription("bogus")).toBe("");
  });
});

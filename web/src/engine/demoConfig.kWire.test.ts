import { describe, expect, it } from "vitest";
import { DEMO_BUDGETS, prepareDemoConfig } from "./demoConfig";

describe("demoConfig K wire default", () => {
  it("DEMO_BUDGETS pins K=30", () => {
    expect(DEMO_BUDGETS.K).toBe(30);
  });

  it("prepareDemoConfig injects K when absent", () => {
    const cfg = prepareDemoConfig({ obs_scenario: "P1" });
    expect(cfg.K).toBe(30);
  });
});

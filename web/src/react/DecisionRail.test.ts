/**
 * T-124 RED (qa-ia): Decision rail — Run + ladder + truth + P&L always visible.
 */
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "../mock/generate";
import type { SectionId } from "../sections";
import type { ScenarioId } from "../types";
import { DecisionRail } from "./DecisionRail";

const LADDER: ScenarioId[] = ["P0", "P1", "F1", "F1s", "F2a", "F2"];

function baseProps(activeSection: SectionId = "physics") {
  return {
    vm: {
      episode_day: 3,
      window_days: 90,
      economics: { ...DEFAULT_ECONOMICS },
      config: { ...DEFAULT_SIM_CONFIG, obs_scenario: "P1" as ScenarioId },
      config_dirty: false,
      pnl_totals: {
        revenue: 100,
        cost: 60,
        profit: 40,
        today_revenue: 10,
        today_cost: 6,
        today_profit: 4,
      },
    },
    showTruth: false,
    onAdvance: vi.fn(),
    onReset: vi.fn(),
    onAutopilotPlay: vi.fn(),
    onAutopilotPause: vi.fn(),
    onSetObsScenario: vi.fn(),
    onShowTruthChange: vi.fn(),
    orderQty: 16,
    onOrderChange: vi.fn(),
    activeSection,
  };
}

describe("DecisionRail (T-124 AC-ia)", () => {
  it("is a sticky aside with Run controls, obs ladder chips, truth toggle, consolidated P&L", () => {
    const props = baseProps();
    render(createElement(DecisionRail, props));

    const rail = document.querySelector("aside.decision-rail");
    expect(rail).not.toBeNull();
    expect(rail?.className).toMatch(/decision-rail|sticky/);

    expect(
      screen.getByRole("button", { name: /advance/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reset/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/order quantity/i)).toBeInTheDocument();
    expect(document.querySelector("#order-num")).toHaveValue(16);

    for (const id of LADDER) {
      expect(document.querySelector(`[data-obs="${id}"]`)).not.toBeNull();
    }

    const truth = screen.getByRole("switch", { name: /truth|true state/i });
    expect(truth).toBeInTheDocument();

    // T-127: consolidated P&L moved to EconomicsPane; Run rail keeps tradeoff charts.
    expect(document.querySelector(".tradeoff-charts, #tradeoff-curve-host")).not.toBeNull();
  });

  it("updates order quantity when the slider moves", () => {
    const props = baseProps();
    render(createElement(DecisionRail, props));

    const slider = document.querySelector("#order-range") as HTMLInputElement;
    fireEvent.input(slider, { target: { value: "32" } });
    expect(props.onOrderChange).toHaveBeenCalledWith(32);
  });

  it("keeps observation ladder chips visible when active section is not Belief", () => {
    const props = baseProps("physics");
    render(createElement(DecisionRail, props));

    const chips = document.querySelectorAll("[data-obs]");
    expect(chips.length).toBe(LADDER.length);
    expect(
      document.querySelector('.controls-block[data-section="observation"] [data-obs]'),
    ).toBeNull();

    const f2 = document.querySelector('[data-obs="F2"]') as HTMLButtonElement;
    fireEvent.click(f2);
    expect(props.onSetObsScenario).toHaveBeenCalledWith("F2");
  });
});

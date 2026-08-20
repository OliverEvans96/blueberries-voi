/**
 * T-124 / T-135: Decision rail — scan-model toggles + truth + tradeoff charts.
 */
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "../mock/generate";
import type { SectionId } from "../sections";
import { DecisionRail } from "./DecisionRail";

function baseProps(activeSection: SectionId = "physics") {
  return {
    vm: {
      episode_day: 3,
      window_days: 90,
      economics: { ...DEFAULT_ECONOMICS },
      config: { ...DEFAULT_SIM_CONFIG },
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
    onSetObsChannels: vi.fn(),
    onSetObsPreset: vi.fn(),
    onShowTruthChange: vi.fn(),
    orderQty: 16,
    activeSection,
  };
}

describe("DecisionRail (T-135 obs channels)", () => {
  it("renders scan-model toggle groups and preset select", () => {
    const props = baseProps();
    render(createElement(DecisionRail, props));

    const rail = document.querySelector("aside.decision-rail");
    expect(rail).not.toBeNull();
    expect(document.querySelector("[data-testid='obs-channels']")).not.toBeNull();
    expect(document.querySelectorAll("[data-obs-code-type]").length).toBe(2);
    expect(document.querySelector("[data-obs-scan-waste]")).not.toBeNull();
    expect(document.querySelectorAll("[data-obs-delivery-history]").length).toBe(3);
    expect(document.getElementById("obs-preset-select")).not.toBeNull();

    const truth = screen.getByRole("switch", { name: /truth|true state/i });
    expect(truth).toBeInTheDocument();
    expect(document.querySelector(".tradeoff-charts, #tradeoff-curve-host")).not.toBeNull();
  });

  it("preset select calls onSetObsPreset", () => {
    const props = baseProps("physics");
    render(createElement(DecisionRail, props));

    const select = document.getElementById("obs-preset-select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "F2" } });
    expect(props.onSetObsPreset).toHaveBeenCalledWith("F2");
  });

  it("code type toggle calls onSetObsChannels", () => {
    const props = baseProps();
    render(createElement(DecisionRail, props));

    const gsin = document.querySelector(
      '[data-obs-code-type="gsin"]',
    ) as HTMLButtonElement;
    fireEvent.click(gsin);
    expect(props.onSetObsChannels).toHaveBeenCalledWith(
      expect.objectContaining({ code_type: "gsin" }),
    );
  });
});

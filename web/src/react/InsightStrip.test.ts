/**
 * T-124 RED (qa-ia): Insight strip — episode context + scenario title + profit.
 */
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "../mock/generate";
import type { ScheduleWire, ViewModel } from "../types";
import { InsightStrip } from "./InsightStrip";

const SCHEDULE: ScheduleWire = {
  delivery_weekdays: [0, 2, 4],
  order_weekdays: [6, 1, 3],
  lead_time_days: 1,
  epoch: "2024-01-06",
};

function sampleViewModel(overrides: Partial<ViewModel> = {}): ViewModel {
  return {
    episode_day: 12,
    window_days: 90,
    history: [],
    economics: { ...DEFAULT_ECONOMICS },
    config: { ...DEFAULT_SIM_CONFIG, obs_scenario: "P1" },
    config_dirty: false,
    pnl_series: [],
    pnl_totals: {
      revenue: 1200,
      cost: 800,
      profit: 400,
      today_revenue: 50,
      today_cost: 30,
      today_profit: 20,
    },
    belief: {
      f_edges: [0, 0.5, 1],
      count_edges: [0, 1],
      density: [[0.5]],
    },
    live_lots: [],
    belief_history: [],
    on_hand: 40,
    effective_inv: 40,
    pipeline: [],
    case_size: 8,
    pending_order: 0,
    demand_summary: null,
    schedule: SCHEDULE,
    ...overrides,
  };
}

describe("InsightStrip (T-124 AC-ia)", () => {
  it("renders episode day N/90, weekday, MWF delivery hint, scenario title, episode profit", () => {
    render(
      createElement(InsightStrip, {
        vm: sampleViewModel(),
        schedule: SCHEDULE,
      }),
    );

    expect(screen.getByText(/12\s*\/\s*90/)).toBeInTheDocument();
    expect(screen.getByText(/Mon|Tue|Wed|Thu|Fri|Sat|Sun/)).toBeInTheDocument();
    expect(
      screen.getByText(/MWF|Mon.*Wed.*Fri|delivery/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Shrink gun/i)).toBeInTheDocument();
    expect(screen.getByText(/\$400\.00|\$400/)).toBeInTheDocument();
  });

  it("uses ADR 0110 locked scenario title for the active obs_scenario", () => {
    render(
      createElement(InsightStrip, {
        vm: sampleViewModel({
          config: { ...DEFAULT_SIM_CONFIG, obs_scenario: "F2a" },
        }),
        schedule: SCHEDULE,
      }),
    );
    expect(screen.getByText(/Pack date on ASN/i)).toBeInTheDocument();
  });
});

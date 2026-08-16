/**
 * T-127 RED (qa-tradeoff-ui): DecisionRail tradeoff mini-charts.
 */
// @vitest-environment jsdom
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "../mock/generate";
import { DecisionRail } from "./DecisionRail";

const HERE = dirname(fileURLToPath(import.meta.url));
const CURVE_TS = join(HERE, "../charts/tradeoffCurve.ts");
const HIST_TS = join(HERE, "../charts/tradeoffHistogram.ts");

const FIXTURE_CANDIDATES = [
  {
    q: 0,
    waste_mean: 1,
    waste_p10: 0,
    waste_p50: 1,
    waste_p90: 2,
    missed_mean: 5,
    missed_p10: 3,
    missed_p50: 5,
    missed_p90: 8,
    joint_hist: { waste_bins: [0, 1, 2], missed_bins: [0, 5, 10], counts: [[1, 0], [0, 1]] },
  },
  {
    q: 16,
    waste_mean: 2,
    waste_p10: 1,
    waste_p50: 2,
    waste_p90: 4,
    missed_mean: 3,
    missed_p10: 1,
    missed_p50: 3,
    missed_p90: 6,
    joint_hist: { waste_bins: [0, 2, 4], missed_bins: [0, 3, 6], counts: [[0, 1], [1, 0]] },
  },
];

function baseProps() {
  return {
    vm: {
      episode_day: 3,
      window_days: 90,
      economics: { ...DEFAULT_ECONOMICS },
      config: { ...DEFAULT_SIM_CONFIG, obs_scenario: "P1" as const },
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
    activeSection: "physics" as const,
    tradeoffForecast: { candidates: FIXTURE_CANDIDATES },
  };
}

describe("DecisionRail tradeoff charts (T-127 AC-tradeoff-ui)", () => {
  it("tradeoffCurve.ts and tradeoffHistogram.ts exist", () => {
    expect(existsSync(CURVE_TS)).toBe(true);
    expect(existsSync(HIST_TS)).toBe(true);
  });

  it("renders Option A curve host with p10-p90 bands and order marker", () => {
    render(createElement(DecisionRail, baseProps()));
    const curve = document.querySelector(
      "#tradeoff-curve-host, [data-testid='tradeoff-curve'], .tradeoff-curve",
    );
    expect(curve).not.toBeNull();
    expect(curve?.querySelector("svg")).not.toBeNull();
    expect(
      curve?.querySelector("[data-order-marker], .order-q-marker"),
    ).not.toBeNull();
  });

  it("renders Option B joint histogram for nearest candidate q", () => {
    render(createElement(DecisionRail, baseProps()));
    const hist = document.querySelector(
      "#tradeoff-histogram-host, [data-testid='tradeoff-histogram'], .tradeoff-histogram",
    );
    expect(hist).not.toBeNull();
    expect(hist?.querySelector("svg")).not.toBeNull();
  });

  it("slider drag updates marker via lookup only — no adapter refetch prop", () => {
    const onFetch = vi.fn();
    const props = { ...baseProps(), onTradeoffRefetch: onFetch };
    render(createElement(DecisionRail, props));
    const slider = document.querySelector("#order-range") as HTMLInputElement;
    fireEvent.input(slider, { target: { value: "32" } });
    expect(props.onOrderChange).toHaveBeenCalled();
    expect(onFetch).not.toHaveBeenCalled();
  });

  it("DecisionRail.tsx wires tradeoff chart modules", () => {
    const src = readFileSync(join(HERE, "DecisionRail.tsx"), "utf8");
    expect(src).toMatch(/tradeoffCurve|renderTradeoffCurve/);
    expect(src).toMatch(/tradeoffHistogram|renderTradeoffHistogram/);
  });
});

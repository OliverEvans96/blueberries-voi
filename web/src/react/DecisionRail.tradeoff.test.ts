/**
 * T-127 RED (qa-tradeoff-ui): DecisionRail tradeoff mini-charts.
 */
// @vitest-environment jsdom
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { render } from "@testing-library/react";
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
    onSetObsScenario: vi.fn(),
    onShowTruthChange: vi.fn(),
    orderQty: 16,
    activeSection: "physics" as const,
    tradeoffForecasts: FIXTURE_CANDIDATES,
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

  it("order-q-marker follows the orderQty prop via lookup only — no adapter refetch prop", () => {
    // T-127 layout v2: the order-quantity slider itself moved to OperatorBar
    // (see OperatorBar.test.ts "updates order quantity when the slider
    // moves"); DecisionRail only needs to re-render its marker/lookup from
    // the orderQty prop it's given, with no extra refetch side channel.
    const onFetch = vi.fn();
    const props = { ...baseProps(), onTradeoffRefetch: onFetch };
    const { rerender } = render(createElement(DecisionRail, props));
    const markerBefore = document
      .querySelector("#tradeoff-curve-host .order-q-marker")
      ?.getAttribute("data-order-q");
    expect(markerBefore).toBe("16");

    rerender(createElement(DecisionRail, { ...props, orderQty: 32 }));
    const markerAfter = document
      .querySelector("#tradeoff-curve-host .order-q-marker")
      ?.getAttribute("data-order-q");
    expect(markerAfter).toBe("32");
    expect(onFetch).not.toHaveBeenCalled();
  });

  it("DecisionRail.tsx wires tradeoff chart modules", () => {
    const src = readFileSync(join(HERE, "DecisionRail.tsx"), "utf8");
    expect(src).toMatch(/tradeoffCurve|renderTradeoffCurve/);
    expect(src).toMatch(/tradeoffHistogram|renderTradeoffHistogram/);
  });
});

/**
 * T-126 RED (qa-dayinspector): DayInspector becomes a cursor-anchored hover tooltip.
 *
 * Positioning contract for implementer: `.day-inspector-tooltip` uses inline
 * `left` / `top` derived from `point.clientX` / `point.clientY` with a fixed
 * +12px offset so the tooltip sits just below-right of the cursor.
 */
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "../mock/generate";
import type { Day, ViewModel } from "../types";
import { DayInspector } from "./DayInspector";

/** Contract from AC-dayinspector / spec interfaces table. */
type HoverPoint = { clientX: number; clientY: number } | null;

type DayInspectorProps = {
  day: number | null;
  point: HoverPoint;
  vm: ViewModel;
};

function sampleViewModel(overrides: Partial<ViewModel> = {}): ViewModel {
  const historyDay: Day = {
    day: 7,
    lots: [],
    sales_total: 42,
    waste_total: 3,
    demand: 45,
    order_qty: 16,
    arrivals: 0,
    stockout: 1,
    f_at_receipt: null,
  };

  return {
    episode_day: 7,
    window_days: 90,
    history: [historyDay],
    economics: { ...DEFAULT_ECONOMICS },
    config: { ...DEFAULT_SIM_CONFIG },
    config_dirty: false,
    pnl_series: [],
    pnl_totals: {
      revenue: 0,
      cost: 0,
      profit: 0,
      today_revenue: 0,
      today_cost: 0,
      today_profit: 0,
    },
    belief: {
      f_edges: [0, 1, 2],
      count_edges: [0, 1],
      density: [[0.2], [0.5], [0.3]],
      f_marginal: [0.2, 0.5, 0.3],
    },
    live_lots: [],
    belief_history: [],
    on_hand: 0,
    effective_inv: 0,
    pipeline: [],
    case_size: 8,
    pending_order: 0,
    demand_summary: null,
    schedule: null,
    ...overrides,
  };
}

function renderInspector(props: DayInspectorProps) {
  return render(createElement(DayInspector, props as never));
}

describe("DayInspector (T-126 AC-dayinspector)", () => {
  it("renders nothing when day is null (no idle empty-state block)", () => {
    const { container } = renderInspector({
      day: null,
      point: null,
      vm: sampleViewModel(),
    });

    expect(container.firstChild).toBeNull();
    expect(document.querySelector(".day-inspector--empty")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("renders nothing when point is null even if day is set", () => {
    const { container } = renderInspector({
      day: 7,
      point: null,
      vm: sampleViewModel(),
    });

    expect(container.firstChild).toBeNull();
    expect(screen.queryByText(/Day 7/)).toBeNull();
  });

  it("renders a positioned tooltip with day stats and belief one-liner", () => {
    renderInspector({
      day: 7,
      point: { clientX: 200, clientY: 150 },
      vm: sampleViewModel(),
    });

    const tooltip = document.querySelector(".day-inspector-tooltip");
    expect(tooltip).not.toBeNull();
    expect(tooltip).toHaveAttribute("role", "status");
    expect(tooltip).toHaveAttribute("data-day", "7");

    expect(screen.getByText("Day 7")).toBeInTheDocument();
    expect(screen.getByText("Sales: 42")).toBeInTheDocument();
    expect(screen.getByText("Waste: 3")).toBeInTheDocument();
    expect(screen.getByText("Stockout: 1")).toBeInTheDocument();
    expect(screen.getByText("Order qty: 16")).toBeInTheDocument();
    expect(
      screen.getByText("Belief peaks near freshness bin 1."),
    ).toBeInTheDocument();
  });

  it("positions the tooltip from point.clientX/clientY with a +12px offset", () => {
    renderInspector({
      day: 7,
      point: { clientX: 100, clientY: 80 },
      vm: sampleViewModel(),
    });

    const first = document.querySelector(
      ".day-inspector-tooltip",
    ) as HTMLElement;
    expect(first).not.toBeNull();
    expect(first.style.left).toBe("112px");
    expect(first.style.top).toBe("92px");

    renderInspector({
      day: 7,
      point: { clientX: 240, clientY: 160 },
      vm: sampleViewModel(),
    });

    const second = document.querySelectorAll(".day-inspector-tooltip")[1] as
      | HTMLElement
      | undefined;
    expect(second).toBeDefined();
    expect(second!.style.left).toBe("252px");
    expect(second!.style.top).toBe("172px");
  });

  it("shows the no-history fallback inside the tooltip when day has no matching row", () => {
    renderInspector({
      day: 99,
      point: { clientX: 50, clientY: 50 },
      vm: sampleViewModel({ history: [] }),
    });

    const tooltip = document.querySelector(".day-inspector-tooltip");
    expect(tooltip).not.toBeNull();
    expect(screen.getByText("Day 99 — no history yet.")).toBeInTheDocument();
  });

  it("uses the default belief one-liner when f_marginal is absent", () => {
    renderInspector({
      day: 7,
      point: { clientX: 10, clientY: 10 },
      vm: sampleViewModel({
        belief: {
          f_edges: [0, 1],
          count_edges: [0, 1],
          density: [[0.5]],
        },
      }),
    });

    expect(document.querySelector(".day-inspector-tooltip")).not.toBeNull();
    expect(
      screen.getByText("Belief updating from observed sales and shrink."),
    ).toBeInTheDocument();
  });
});

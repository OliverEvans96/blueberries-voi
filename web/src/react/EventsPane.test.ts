/**
 * T-148: EventsPane — 5-day window, Delivered | Sold | Spoiled columns.
 */
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";
import { channelsForPreset } from "../obsMask";
import { EventsPane } from "./EventsPane";
import type { ScheduleWire } from "../engine/types";

type MaskedDayWire = {
  day: number;
  arrivals: number;
  sales_total?: number | null;
  waste_total?: number | null;
  sales_by?: number[] | null;
  waste_by?: number[] | null;
  lot_ids?: number[] | null;
  arrival_lot_ids?: number[] | null;
  pack_date_days?: number | null;
};

const SCHEDULE: ScheduleWire = {
  delivery_weekdays: [0, 2, 4],
  order_weekdays: [5, 1, 3],
  lead_time_days: 2,
  epoch: "2024-01-01",
};

const P0_DAY: MaskedDayWire = {
  day: 1,
  arrivals: 16,
  sales_total: 10,
  waste_total: null,
};

const F2_DAY: MaskedDayWire = {
  day: 2,
  arrivals: 8,
  sales_total: 6,
  waste_total: 1,
  sales_by: [4, 2],
  waste_by: [0, 1],
  lot_ids: [101, 102],
  pack_date_days: 3,
};

describe("EventsPane (T-148 v6)", () => {
  it("shows last five days from max(1, episode_day-4) through episode_day", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 7, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [],
      }),
    );
    const cards = container.querySelectorAll(".events-day-card");
    expect(cards.length).toBe(5);
    expect(cards[0]?.getAttribute("data-day")).toBe("3");
    expect(cards[4]?.getAttribute("data-day")).toBe("7");
  });

  it("renders three column tables per day", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 3, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY, F2_DAY],
      }),
    );
    expect(container.querySelectorAll("[data-testid='events-columns']").length).toBe(3);
    expect(container.querySelectorAll("[data-testid='events-col-delivered']").length).toBe(3);
    expect(container.querySelectorAll("[data-testid='events-col-sold']").length).toBe(3);
    expect(container.querySelectorAll("[data-testid='events-col-spoiled']").length).toBe(3);
  });

  it("P0 hides waste — shows not-observed in spoiled column", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 1, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
      }),
    );
    expect(screen.getByText(/not observed at this rung/i)).toBeInTheDocument();
  });

  it("F2 shows lot rows in sold and spoiled columns", () => {
    render(
      createElement(EventsPane, {
        vm: {
          episode_day: 2,
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F2",
            obs_channels: channelsForPreset("F2"),
          },
        },
        schedule: SCHEDULE,
        events: [F2_DAY],
      }),
    );
    expect(screen.getAllByText("Lot 101").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Lot 102").length).toBeGreaterThan(0);
    expect(screen.getByText(/pack date 3 days/i)).toBeInTheDocument();
  });

  it("shows delivery and order chips from schedule", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 1, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
      }),
    );
    expect(screen.getByText("Delivery")).toBeInTheDocument();
    expect(screen.queryByText("Order")).toBeNull();
  });

  it("shows loading state when loading=true", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 1, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [],
        loading: true,
      }),
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});

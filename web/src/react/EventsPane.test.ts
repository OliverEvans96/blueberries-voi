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
  arrivals_by?: number[] | null;
  lot_ids?: number[] | null;
  arrival_lot_ids?: number[] | null;
  pack_date_days?: number | null;
  temp_times_d?: number[] | null;
  temp_temps_c?: number[] | null;
  temp_traces_by_lot?: Array<{
    lot_id: number;
    times_d: number[];
    temps_c: number[];
  }> | null;
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
  it("shows last five completed days newest-first, excluding today", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 7, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [],
      }),
    );
    const cards = container.querySelectorAll(".events-day-card");
    expect(cards.length).toBe(5);
    expect(cards[0]?.getAttribute("data-day")).toBe("6");
    expect(cards[4]?.getAttribute("data-day")).toBe("2");
  });

  it("renders three column tables per day", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 3, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY, F2_DAY],
      }),
    );
    expect(container.querySelectorAll("[data-testid='events-columns']").length).toBe(2);
    expect(container.querySelectorAll("[data-testid='events-col-delivered']").length).toBe(2);
    expect(container.querySelectorAll("[data-testid='events-col-sold']").length).toBe(2);
    expect(container.querySelectorAll("[data-testid='events-col-spoiled']").length).toBe(2);
  });

  it("P0 hides waste — shows not-observed in spoiled column", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
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
          episode_day: 3,
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

  it("delivery lot rows sum to delivery total", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: {
          episode_day: 3,
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F1",
            obs_channels: channelsForPreset("F1"),
          },
        },
        schedule: SCHEDULE,
        events: [
          {
            day: 2,
            arrivals: 16,
            arrival_lot_ids: [201, 202],
            arrivals_by: [10, 6],
            sales_total: 4,
            waste_total: 0,
          },
        ],
      }),
    );
    const deliveredCol = container.querySelector(
      "[data-testid='events-col-delivered']",
    );
    const lotQty = Array.from(
      deliveredCol?.querySelectorAll(".events-table-lot td") ?? [],
    ).map((el) => Number(el.textContent));
    expect(lotQty.reduce((s, n) => s + n, 0)).toBe(16);
  });

  it("shows delivery and order markers on the left", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
      }),
    );
    expect(screen.getByText("delivery day")).toBeInTheDocument();
    expect(screen.queryByText("order day")).toBeNull();
  });

  it("shows day number only in heading", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
      }),
    );
    expect(screen.getByRole("heading", { level: 3, name: "Day 1" })).toBeInTheDocument();
    expect(screen.queryByText(/Monday|Jan/i)).toBeNull();
  });

  it("shows initial loading only when there is no event data", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [],
        loading: true,
      }),
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("keeps stale cards visible while refreshing", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 3, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
        refreshing: true,
      }),
    );
    expect(screen.getByText("Day 1")).toBeInTheDocument();
    expect(screen.getByText(/updating/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Loading events/i)).toBeNull();
  });

  it("F3 delivery day shows temperature history chart", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: {
          episode_day: 3,
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F3",
            obs_channels: channelsForPreset("F3"),
          },
        },
        schedule: SCHEDULE,
        events: [
          {
            day: 1,
            arrivals: 8,
            arrival_lot_ids: [301, 302],
            arrivals_by: [5, 3],
            sales_total: 4,
            waste_total: 0,
            temp_traces_by_lot: [
              {
                lot_id: 301,
                times_d: [-3, -2, -1, 0],
                temps_c: [2, 2.2, 2.4, 2.6],
              },
              {
                lot_id: 302,
                times_d: [-3, -2, -1, 0],
                temps_c: [2.5, 2.7, 2.9, 3.1],
              },
            ],
          },
        ],
      }),
    );
    expect(screen.getByText(/temperature history/i)).toBeInTheDocument();
    expect(container.querySelector(".delivery-temp-chart--multi")).not.toBeNull();
  });

  it("F2a shows pack date but not age at receipt", () => {
    render(
      createElement(EventsPane, {
        vm: {
          episode_day: 4,
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F2a",
            obs_channels: channelsForPreset("F2a"),
          },
        },
        schedule: SCHEDULE,
        events: [
          {
            day: 3,
            arrivals: 12,
            sales_total: 8,
            waste_total: 1,
            pack_date_days: 4,
          },
        ],
      }),
    );
    expect(screen.getByText(/4 days/i)).toBeInTheDocument();
    expect(screen.queryByText(/age at receipt/i)).toBeNull();
  });

  it("F2 shows pack date on delivery days only", () => {
    render(
      createElement(EventsPane, {
        vm: {
          episode_day: 4,
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F2",
            obs_channels: channelsForPreset("F2"),
          },
        },
        schedule: SCHEDULE,
        events: [
          {
            day: 3,
            arrivals: 12,
            sales_total: 4,
            waste_total: 1,
            sales_by: [4],
            waste_by: [1],
            lot_ids: [101],
            pack_date_days: 2,
          },
        ],
      }),
    );
    expect(screen.queryByText(/age at receipt/i)).toBeNull();
    expect(screen.getByText(/pack date/i)).toBeInTheDocument();
  });

  it("F2 delivery day does not show temp chart when history is pack_date", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: {
          episode_day: 3,
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
    expect(screen.queryByText(/temperature history/i)).toBeNull();
    expect(container.querySelector(".delivery-temp-chart--multi")).toBeNull();
  });
});

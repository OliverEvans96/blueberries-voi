/**
 * Event Log pane — 5-day window, Sold | Spoiled main table; delivery/order sections.
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
  pack_date_days?: number | number[] | null;
  pack_dates_by_lot?: number[] | null;
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

describe("EventsPane (Event Log refactor)", () => {
  it("shows last five completed days newest-first, excluding today", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 7, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [],
        orderQtyByDay: new Map(),
      }),
    );
    const cards = container.querySelectorAll(".events-day-card");
    expect(cards.length).toBe(5);
    expect(cards[0]?.getAttribute("data-day")).toBe("6");
    expect(cards[4]?.getAttribute("data-day")).toBe("2");
  });

  it("uses Event Log pane title and aria-label", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [],
        orderQtyByDay: new Map(),
      }),
    );
    expect(screen.getByRole("heading", { level: 2, name: "Event Log" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Event Log" })).toBeInTheDocument();
  });

  it("renders Sold and Spoiled columns only in the main table", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 3, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY, F2_DAY],
        orderQtyByDay: new Map(),
      }),
    );
    expect(container.querySelectorAll("[data-testid='events-columns']").length).toBe(2);
    expect(container.querySelectorAll("[data-testid='events-col-sold']").length).toBe(2);
    expect(container.querySelectorAll("[data-testid='events-col-spoiled']").length).toBe(2);
    expect(container.querySelectorAll("[data-testid='events-col-delivered']").length).toBe(0);
  });

  it("P0 hides waste — shows not-observed in spoiled column", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
        orderQtyByDay: new Map(),
      }),
    );
    expect(screen.getByText(/^not observed$/i)).toBeInTheDocument();
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
        orderQtyByDay: new Map(),
      }),
    );
    expect(screen.getAllByText("Lot 101").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Lot 102").length).toBeGreaterThan(0);
  });

  it("UPC delivery section is one row with Delivered and Pack date columns", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: {
          episode_day: 3,
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F2a",
            obs_channels: channelsForPreset("F2a"),
          },
        },
        schedule: SCHEDULE,
        events: [
          {
            day: 2,
            arrivals: 16,
            sales_total: 4,
            waste_total: 0,
            pack_date_days: 4,
          },
        ],
        orderQtyByDay: new Map(),
      }),
    );
    const delivery = container.querySelector(
      '.events-day-card[data-day="2"] [data-testid="events-delivery-section"]',
    );
    expect(delivery).not.toBeNull();
    expect(delivery!.querySelector(".events-delivery-table--upc")).not.toBeNull();
    expect(delivery!.textContent).toContain("16");
    expect(delivery!.textContent).toContain("4");
    expect(delivery!.querySelectorAll(".events-delivery-table tbody tr").length).toBe(1);
  });

  it("LGTIN delivery section shows per-lot Delivered and Pack date rows", () => {
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
        orderQtyByDay: new Map(),
      }),
    );
    const delivery = container.querySelector(
      '.events-day-card[data-day="2"] [data-testid="events-delivery-section"]',
    );
    expect(delivery).not.toBeNull();
    expect(delivery!.querySelector(".events-delivery-table--lgtin")).not.toBeNull();
    const lotRows = delivery!.querySelectorAll(".events-delivery-table tbody tr");
    expect(lotRows.length).toBe(2);
    expect(delivery!.textContent).toContain("Lot 201");
    expect(delivery!.textContent).toContain("Lot 202");
    expect(delivery!.textContent).toContain("10");
    expect(delivery!.textContent).toContain("6");
  });

  it("does not show delivery section on non-delivery days", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
        orderQtyByDay: new Map(),
      }),
    );
    expect(
      container.querySelector('.events-day-card[data-day="1"] [data-testid="events-delivery-section"]'),
    ).toBeNull();
  });

  it("shows order section with qty on schedule order days", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
        orderQtyByDay: new Map([[1, 24]]),
      }),
    );
    expect(screen.getByText("Ordered: 24")).toBeInTheDocument();
  });

  it("does not show order section on non-order days", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 3, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [{ ...P0_DAY, day: 2 }],
        orderQtyByDay: new Map([[2, 16]]),
      }),
    );
    expect(
      container.querySelector('.events-day-card[data-day="2"] [data-testid="events-order-section"]'),
    ).toBeNull();
  });

  it("does not render standalone pack-date paragraph", () => {
    const { container } = render(
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
        orderQtyByDay: new Map(),
      }),
    );
    expect(container.querySelector(".events-pack-date")).toBeNull();
    expect(screen.queryByText(/packed .* before arrival/i)).toBeNull();
  });

  it("shows delivery and order marker chips to the right of the day heading", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 3, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [{ ...P0_DAY, day: 2 }],
        orderQtyByDay: new Map(),
      }),
    );
    const day2Card = container.querySelector('.events-day-card[data-day="2"]');
    expect(day2Card).not.toBeNull();
    expect(day2Card!.querySelector(".events-day-marker--delivery")).not.toBeNull();
    expect(day2Card!.querySelector(".events-day-marker--order")).toBeNull();
    expect(day2Card!.textContent).toContain("Delivery day");
    expect(day2Card!.textContent).not.toContain("delivery day");

    const header = day2Card!.querySelector(".events-day-header");
    const heading = header?.querySelector(".events-day-heading");
    const markers = header?.querySelector(".events-day-markers");
    expect(heading).not.toBeNull();
    expect(markers).not.toBeNull();
    expect(
      heading!.compareDocumentPosition(markers!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("formats day heading as bold weekday, comma, lowercase day — no parentheses", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
        orderQtyByDay: new Map(),
      }),
    );
    expect(screen.getByRole("heading", { level: 3, name: "Tue, day 1" })).toBeInTheDocument();
    expect(screen.queryByText(/\(day 1\)/i)).toBeNull();
  });

  it("shows initial loading only when there is no event data", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 2, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [],
        orderQtyByDay: new Map(),
        loading: true,
      }),
    );
    expect(screen.getByText(/loading event log/i)).toBeInTheDocument();
  });

  it("keeps stale cards visible while refreshing", () => {
    render(
      createElement(EventsPane, {
        vm: { episode_day: 3, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [P0_DAY],
        orderQtyByDay: new Map(),
        refreshing: true,
      }),
    );
    expect(screen.getByRole("heading", { level: 3, name: "Tue, day 1" })).toBeInTheDocument();
    expect(screen.getByText(/updating/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Loading event log/i)).toBeNull();
  });

  it("F3 delivery day shows temperature history chart and pack date", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: {
          episode_day: 4,
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F3",
            obs_channels: channelsForPreset("F3"),
          },
        },
        schedule: SCHEDULE,
        events: [
          {
            day: 2,
            arrivals: 8,
            arrival_lot_ids: [301, 302],
            arrivals_by: [5, 3],
            sales_total: 4,
            waste_total: 0,
            pack_dates_by_lot: [3, 5],
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
        orderQtyByDay: new Map(),
      }),
    );
    expect(screen.getByText(/temperature history/i)).toBeInTheDocument();
    expect(container.querySelector(".delivery-temp-chart--multi")).not.toBeNull();

    const deliveryTable = container.querySelector(
      '.events-day-card[data-day="2"] .events-delivery-table',
    );
    expect(deliveryTable).not.toBeNull();
    expect(deliveryTable!.textContent).toMatch(/Pack date/);
    expect(deliveryTable!.textContent).toMatch(/3/);
    expect(deliveryTable!.textContent).not.toMatch(/Not observed/);

    const summaries = container.querySelector(
      '[data-testid="events-temp-summaries"]',
    );
    expect(summaries).not.toBeNull();
    const lines = summaries!.querySelectorAll(".events-temp-summary-line");
    expect(lines.length).toBe(2);

    const lot301 = summaries!.querySelector('[data-lot="301"]');
    expect(lot301?.textContent).toMatch(/Lot 301/);
    expect(lot301?.textContent).toMatch(/min\s*2\.0°C/);
    expect(lot301?.textContent).toMatch(/max\s*2\.6°C/);
    expect(lot301?.textContent).toMatch(/mean\s*2\.3°C/);
    expect(lot301?.textContent).toMatch(/std\s*0\.3°C/);

    const lot302 = summaries!.querySelector('[data-lot="302"]');
    expect(lot302?.textContent).toMatch(/Lot 302/);
    expect(lot302?.textContent).toMatch(/min\s*2\.5°C/);
    expect(lot302?.textContent).toMatch(/max\s*3\.1°C/);
    expect(lot302?.textContent).toMatch(/mean\s*2\.8°C/);
    expect(lot302?.textContent).toMatch(/std\s*0\.3°C/);
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
        orderQtyByDay: new Map(),
      }),
    );
    expect(screen.queryByText(/temperature history/i)).toBeNull();
    expect(container.querySelector(".delivery-temp-chart--multi")).toBeNull();
  });

  it("shows the temperature history chart on any day with real arrivals and temp data, even when the schedule delivery-day badge does not cover that day", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: {
          episode_day: 2,
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
            arrival_lot_ids: [401],
            arrivals_by: [8],
            sales_total: 4,
            waste_total: 0,
            temp_traces_by_lot: [
              {
                lot_id: 401,
                times_d: [-3, -2, -1, 0],
                temps_c: [2, 2.2, 2.4, 2.6],
              },
            ],
          },
        ],
        orderQtyByDay: new Map(),
      }),
    );
    expect(screen.getByText(/temperature history/i)).toBeInTheDocument();
    expect(container.querySelector(".events-temp-history")).not.toBeNull();
  });

  it("shows loading skeleton when loading with no events yet", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: { episode_day: 7, config: DEFAULT_SIM_CONFIG },
        schedule: SCHEDULE,
        events: [],
        loading: true,
      }),
    );
    expect(screen.getByTestId("events-loading-placeholder")).toBeInTheDocument();
    expect(container.querySelectorAll(".events-day-card--skeleton").length).toBe(
      3,
    );
    expect(container.querySelectorAll(".events-day-card[data-day]")).toHaveLength(
      0,
    );
  });

  it("LGTIN F2 shows distinct per-lot pack dates from pack_dates_by_lot", () => {
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
        events: [
          {
            day: 2,
            arrivals: 16,
            arrival_lot_ids: [201, 202],
            arrivals_by: [10, 6],
            sales_total: 4,
            waste_total: 0,
            pack_date_days: 3,
            pack_dates_by_lot: [3, 5],
          },
        ],
        orderQtyByDay: new Map(),
      }),
    );
    const delivery = container.querySelector(
      '.events-day-card[data-day="2"] [data-testid="events-delivery-section"]',
    );
    expect(delivery).not.toBeNull();
    const lotRows = delivery!.querySelectorAll(".events-delivery-table tbody tr");
    expect(lotRows.length).toBe(2);
    expect(lotRows[0]?.textContent).toContain("3");
    expect(lotRows[0]?.textContent).not.toContain("5");
    expect(lotRows[1]?.textContent).toContain("5");
    expect(lotRows[1]?.textContent).not.toContain("3, 5");
  });

  it("LGTIN falls back to scalar pack_date_days when pack_dates_by_lot absent", () => {
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
        events: [
          {
            day: 2,
            arrivals: 16,
            arrival_lot_ids: [201, 202],
            arrivals_by: [10, 6],
            sales_total: 4,
            waste_total: 0,
            pack_date_days: 4,
          },
        ],
        orderQtyByDay: new Map(),
      }),
    );
    const delivery = container.querySelector(
      '.events-day-card[data-day="2"] [data-testid="events-delivery-section"]',
    );
    const lotRows = delivery!.querySelectorAll(".events-delivery-table tbody tr");
    expect(lotRows.length).toBe(2);
    expect(lotRows[0]?.textContent).toContain("4");
    expect(lotRows[1]?.textContent).toContain("4");
  });

  it("UPC pack date cell joins multiple scalar dates comma-separated", () => {
    const { container } = render(
      createElement(EventsPane, {
        vm: {
          episode_day: 3,
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F2a",
            obs_channels: channelsForPreset("F2a"),
          },
        },
        schedule: SCHEDULE,
        events: [
          {
            day: 2,
            arrivals: 16,
            sales_total: 4,
            waste_total: 0,
            pack_date_days: [3, 4, 5],
          },
        ],
        orderQtyByDay: new Map(),
      }),
    );
    const delivery = container.querySelector(
      '.events-day-card[data-day="2"] [data-testid="events-delivery-section"]',
    );
    expect(delivery?.textContent).toContain("3, 4, 5");
  });
});

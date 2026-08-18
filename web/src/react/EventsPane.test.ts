/**
 * T-127 RED (qa-events-ui): EventsPane — masked event log cards.
 */
// @vitest-environment jsdom
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "../mock/generate";
import { channelsForPreset } from "../obsMask";

const HERE = dirname(fileURLToPath(import.meta.url));
const MODULE = join(HERE, "EventsPane.tsx");

type MaskedDayWire = {
  day: number;
  arrivals: number;
  sales_total?: number | null;
  waste_total?: number | null;
  sales_by?: number[] | null;
  waste_by?: number[] | null;
  lot_ids?: number[] | null;
  age_at_receipt?: number | null;
  pack_date_days?: number | null;
};

type EventsPaneModule = {
  EventsPane: (props: {
    vm: {
      episode_day: number;
      history: { day: number; missed?: number }[];
      config: { obs_scenario: string };
    };
    showTruth: boolean;
    events: MaskedDayWire[];
    loading?: boolean;
  }) => ReturnType<typeof createElement>;
};

async function loadEventsPane(): Promise<EventsPaneModule | null> {
  if (!existsSync(MODULE)) return null;
  try {
    return (await import(MODULE)) as EventsPaneModule;
  } catch {
    return null;
  }
}

const P0_DAY: MaskedDayWire = {
  day: 1,
  arrivals: 16,
  sales_total: 10,
  waste_total: null,
  sales_by: null,
  waste_by: null,
  lot_ids: null,
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

function baseVm(showTruth = false) {
  return {
    episode_day: 3,
    history: [
      { day: 1, missed: 2 },
      { day: 2, missed: 0 },
      { day: 3, missed: 1 },
    ],
    config: { ...DEFAULT_SIM_CONFIG, obs_scenario: "P0" as const },
    economics: { ...DEFAULT_ECONOMICS },
  };
}

describe("EventsPane (T-127 AC-events-ui)", () => {
  it("exports EventsPane component", async () => {
    const mod = await loadEventsPane();
    expect(mod, "expected web/src/react/EventsPane.tsx").not.toBeNull();
    expect(typeof mod!.EventsPane).toBe("function");
  });

  it("renders one card group per day with day delimiters", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    render(
      createElement(EventsPane, {
        vm: baseVm(),
        showTruth: false,
        events: [P0_DAY, F2_DAY],
      }),
    );
    expect(screen.getAllByText(/day\s*1/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/day\s*2/i).length).toBeGreaterThan(0);
  });

  it("P0 hides waste — shows not-observed, never fabricated zero", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    render(
      createElement(EventsPane, {
        vm: baseVm(),
        showTruth: false,
        events: [P0_DAY],
      }),
    );
    expect(screen.queryByText(/^0$/)).toBeNull();
    expect(
      screen.getByText(/not observed at this rung/i),
    ).toBeInTheDocument();
  });

  it("F2 shows lot maps when masked-in", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    render(
      createElement(EventsPane, {
        vm: {
          ...baseVm(),
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F2",
            obs_channels: channelsForPreset("F2"),
          },
        },
        showTruth: false,
        events: [F2_DAY],
      }),
    );
    expect(screen.getByText(/Lot 101: 4 units/i)).toBeInTheDocument();
    expect(screen.getByText(/Lot 102: 1 unit\b/i)).toBeInTheDocument();
    expect(screen.getByText(/waste/i)).toBeInTheDocument();
    expect(screen.getByText(/pack date 3 days/i)).toBeInTheDocument();
  });

  it("lot breakdown omits zero-quantity lots (T-130)", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    const day: MaskedDayWire = {
      day: 4,
      arrivals: 0,
      sales_total: 6,
      waste_total: 1,
      sales_by: [6, 0, 0],
      waste_by: [0, 1, 0],
      lot_ids: [201, 202, 203],
    };
    render(
      createElement(EventsPane, {
        vm: {
          ...baseVm(),
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F2",
            obs_channels: channelsForPreset("F2"),
          },
        },
        showTruth: false,
        events: [day],
      }),
    );
    expect(screen.getByText(/Lot 201: 6 units/i)).toBeInTheDocument();
    expect(screen.getByText(/Lot 202: 1 unit\b/i)).toBeInTheDocument();
    expect(screen.queryByText(/Lot 203/i)).toBeNull();
  });

  it("sorts day cards latest-first", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    const { container } = render(
      createElement(EventsPane, {
        vm: baseVm(),
        showTruth: false,
        events: [P0_DAY, F2_DAY],
      }),
    );
    const cards = container.querySelectorAll(".events-day-card");
    expect(cards.length).toBe(2);
    expect(cards[0]?.getAttribute("data-day")).toBe("2");
    expect(cards[1]?.getAttribute("data-day")).toBe("1");
    expect(container.querySelectorAll(".events-day-divider").length).toBe(1);
  });

  it("F2a shows pack date but not age at receipt", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    const f2aDay: MaskedDayWire = {
      day: 3,
      arrivals: 12,
      sales_total: 8,
      waste_total: 1,
      sales_by: null,
      waste_by: null,
      lot_ids: null,
      pack_date_days: 4,
      age_at_receipt: null,
    };
    render(
      createElement(EventsPane, {
        vm: {
          ...baseVm(),
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F2a",
            obs_channels: channelsForPreset("F2a"),
          },
        },
        showTruth: false,
        events: [f2aDay],
      }),
    );
    expect(screen.getByText(/4 days/i)).toBeInTheDocument();
    expect(screen.queryByText(/age at receipt/i)).toBeNull();
    expect(screen.queryByText(/1\.5/)).toBeNull();
  });

  it("F2 does not surface age_at_receipt at the channel mask rung", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    const f2NonDelivery: MaskedDayWire = {
      day: 3,
      arrivals: 0,
      sales_total: 4,
      waste_total: 1,
      sales_by: [4],
      waste_by: [1],
      lot_ids: [101],
      age_at_receipt: 1.5,
      pack_date_days: 2,
    };
    render(
      createElement(EventsPane, {
        vm: {
          ...baseVm(),
          config: {
            ...DEFAULT_SIM_CONFIG,
            obs_scenario: "F2",
            obs_channels: channelsForPreset("F2"),
          },
        },
        showTruth: false,
        events: [f2NonDelivery],
      }),
    );
    expect(screen.queryByText(/age at receipt/i)).toBeNull();
    expect(screen.getByText(/pack date/i)).toBeInTheDocument();
  });

  it("delivery day shows illustrative temp chart", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    const { container } = render(
      createElement(EventsPane, {
        vm: baseVm(),
        showTruth: false,
        events: [F2_DAY],
      }),
    );
    expect(screen.getByText(/temp\. history \(illustrative\)/i)).toBeInTheDocument();
    expect(container.querySelector(".events-temp-chart-host svg")).not.toBeNull();
    expect(
      container.querySelector(".delivery-temp-line, [data-series='temp']"),
    ).not.toBeNull();
  });

  it("P0 hides per-lot breakdown without lot_ids", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    const { container } = render(
      createElement(EventsPane, {
        vm: baseVm(),
        showTruth: false,
        events: [P0_DAY],
      }),
    );
    expect(container.querySelector(".events-breakdown")).toBeNull();
  });

  it("stockout row hidden when showTruth=false", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    render(
      createElement(EventsPane, {
        vm: baseVm(false),
        showTruth: false,
        events: [P0_DAY],
      }),
    );
    expect(screen.queryByText(/stockout|missed sales/i)).toBeNull();
  });

  it("stockout row visible when showTruth=true", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    render(
      createElement(EventsPane, {
        vm: baseVm(true),
        showTruth: true,
        events: [P0_DAY],
        loading: false,
      }),
    );
    expect(screen.getByText(/stockout|missed/i)).toBeInTheDocument();
  });

  it("shows loading state when loading=true", async () => {
    const { EventsPane } = (await loadEventsPane())!;
    render(
      createElement(EventsPane, {
        vm: baseVm(),
        showTruth: false,
        events: [],
        loading: true,
      }),
    );
    expect(
      screen.getByText(/loading|fetching/i) ??
        document.querySelector("[data-loading]"),
    ).toBeTruthy();
  });
});

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
  age_at_receipt: 1.5,
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
        vm: { ...baseVm(), config: { ...DEFAULT_SIM_CONFIG, obs_scenario: "F2" } },
        showTruth: false,
        events: [F2_DAY],
      }),
    );
    expect(screen.getByText(/101|lot/i)).toBeInTheDocument();
    expect(screen.getByText(/waste/i)).toBeInTheDocument();
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

/**
 * T-151: MockAdapter.events() must mask from live obs_channels, not stale obs_scenario.
 */
import { describe, expect, it } from "vitest";
import type { Day } from "../types";
import { MockAdapter } from "./adapter";

function seedDeliveryDay(adapter: MockAdapter, day: Day): void {
  const internal = adapter as unknown as { state: { history: Day[]; day: number } };
  internal.state.history.push(day);
  internal.state.day = day.day + 1;
}

describe("MockAdapter.events() observation masking", () => {
  it("exposes temperature history when obs_channels enable it despite stale obs_scenario", async () => {
    const adapter = new MockAdapter(42);
    await adapter.init({});
    adapter.setConfig({
      obs_scenario: "P1",
      obs_channels: {
        code_type: "upc",
        scan_waste: true,
        delivery_history: "temperature_history",
      },
    });

    seedDeliveryDay(adapter, {
      day: 2,
      arrivals: 16,
      lots: [{ lot_id: 1, n: 16, mean_f: 0.85 }],
      units: [],
      unit_exits: [],
      sales_total: 5,
      waste_total: 0,
      demand: 10,
      order_qty: 16,
      stockout: 0,
      f_at_receipt: 0.85,
    });

    const { days } = await adapter.events({ since_day: 0 });
    const deliveryDay = days.find((d) => d.day === 2);

    expect(deliveryDay).toBeDefined();
    expect(deliveryDay!.arrivals).toBe(16);
    expect(deliveryDay!.temp_times_d).not.toBeNull();
    expect(deliveryDay!.temp_temps_c).not.toBeNull();
    expect(deliveryDay!.temp_times_d!.length).toBeGreaterThan(0);
    expect(deliveryDay!.temp_temps_c!.length).toBeGreaterThan(0);
  });
});

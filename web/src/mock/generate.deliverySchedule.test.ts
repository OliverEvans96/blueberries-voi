/**
 * T-151 (bugfix): mock physics engine's order-day weekday gate must use the
 * same Monday=0 convention (day 1 == Monday) as `scheduleFromConfig` /
 * `EventsPane`'s `isDeliveryDay`, so arrivals actually land on the days the
 * UI labels "delivery day". Regression for the delivery-temp-chart never
 * rendering: `showTempChart` requires `deliveryDay && deliveredTotal > 0`,
 * which was never simultaneously true because `runDay` gated orders on
 * `day % 7` instead of the `(day - 1) % 7` convention used everywhere else.
 */
import { describe, expect, it } from "vitest";
import { scheduleFromConfig } from "../calendar/weekCalendar";
import { DEFAULT_SIM_CONFIG, createInitialState, stepSimulation } from "./generate";

function monday0Weekday(day: number): number {
  return (((day - 1) % 7) + 7) % 7;
}

describe("mock physics engine delivery-day alignment (T-151 bugfix)", () => {
  it("arrivals land on the days the schedule labels as delivery days", () => {
    const cfg = { ...DEFAULT_SIM_CONFIG };
    const schedule = scheduleFromConfig(cfg);
    let state = createInitialState(cfg);
    const orderQty = cfg.case_size * 5;

    const arrivalDays: number[] = [];
    for (let i = 0; i < 14; i++) {
      const { state: next, dayRecord } = stepSimulation(state, orderQty, cfg);
      state = next;
      if (dayRecord.arrivals > 0) {
        arrivalDays.push(dayRecord.day);
      }
    }

    expect(arrivalDays.length).toBeGreaterThan(0);
    for (const day of arrivalDays) {
      expect(schedule.delivery_weekdays).toContain(monday0Weekday(day));
    }
  });
});

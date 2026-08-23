/**
 * T-151 (bugfix): the Events pane's "delivery day" / "order day" badges
 * must line up with the days the real simulation flow actually places
 * orders / receives arrivals on.
 *
 * The studio's "Place Order" control (`advanceEpisode` in studioLogic.ts)
 * doesn't step one raw day at a time — it calls `buildStepNOrders`, which
 * picks the next order day via `nextOrderDayFromSchedule` /
 * `weekdayMonday0` (epoch-anchored: `schedule.epoch` "2024-01-01" is a
 * Monday, so day 0 == Monday). This is the authoritative weekday
 * convention: `runDay`'s own `day % 7` order gate already agrees with it
 * (epoch day 0 == weekday 0), so `generate.ts` needs no change.
 *
 * `EventsPane.tsx` used to compute badges with its own local
 * `(day - 1) % 7` helper — a day 1 == Monday convention that disagreed
 * with the epoch anchor by exactly one day, so its "delivery day" badge
 * never coincided with an actual arrival. The regression coverage below
 * drives the real `buildStepNOrders` + `stepSimulation` round trip and
 * checks arrivals against the authoritative `weekdayMonday0`, so a
 * reintroduced mismatch between EventsPane's badge convention and the
 * real order/arrival timing would be caught by `EventsPane.test.ts`
 * (badge-vs-schedule) even though this file only exercises the physics
 * engine.
 */
import { describe, expect, it } from "vitest";
import { scheduleFromConfig } from "../calendar/weekCalendar";
import { buildStepNOrders, weekdayMonday0 } from "../calendar/nextOrderAdvance";
import { DEFAULT_SIM_CONFIG, createInitialState, stepSimulation } from "./generate";

describe("mock physics engine delivery-day alignment (T-151 bugfix)", () => {
  it("real Place-Order flow (buildStepNOrders + stepSimulation) lands arrivals on schedule delivery days", () => {
    const cfg = { ...DEFAULT_SIM_CONFIG };
    const schedule = scheduleFromConfig(cfg);
    let state = createInitialState(cfg);
    let currentDay = state.day;

    const arrivalDays: number[] = [];
    for (let click = 0; click < 6; click++) {
      const orders = buildStepNOrders(currentDay, cfg.case_size * 3, schedule);
      for (const orderQty of orders) {
        const { state: next, dayRecord } = stepSimulation(state, orderQty, cfg);
        state = next;
        if (dayRecord.arrivals > 0) {
          arrivalDays.push(dayRecord.day);
        }
      }
      currentDay = state.day;
    }

    expect(arrivalDays.length).toBeGreaterThan(0);
    for (const day of arrivalDays) {
      expect(schedule.delivery_weekdays).toContain(weekdayMonday0(day, schedule));
    }
  });
});

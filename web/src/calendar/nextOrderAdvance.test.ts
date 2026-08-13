/**
 * T-086 RED: next-order-day advance helpers consume Snapshot schedule fields
 * (ADR 0111) — build step_n orders, weekday labels, LT=1 pipeline hint.
 *
 * Implement owns `web/src/calendar/nextOrderAdvance.ts` (or equivalent export
 * path). Dynamic import keeps missing-module RED as an assertion failure.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { ScheduleWire } from "../engine/types";

const HERE = dirname(fileURLToPath(import.meta.url));
const CANDIDATE_MODULES = [
  join(HERE, "nextOrderAdvance.ts"),
  join(HERE, "index.ts"),
  join(HERE, "../engine/nextOrderAdvance.ts"),
];

const DEFAULT_SCHEDULE: ScheduleWire = {
  delivery_weekdays: [0, 2, 4],
  order_weekdays: [6, 1, 3],
  lead_time_days: 1,
  epoch: "2024-01-01",
};

const WEEKDAY_NAMES = [
  "Mon",
  "Tue",
  "Wed",
  "Thu",
  "Fri",
  "Sat",
  "Sun",
] as const;

type NextOrderAdvanceModule = {
  buildStepNOrders?: (
    currentDay: number,
    orderQty: number,
    schedule: ScheduleWire,
  ) => number[];
  nextOrderDayFromSchedule?: (
    currentDay: number,
    schedule: ScheduleWire,
  ) => number;
  weekdayLabel?: (episodeDay: number, schedule: ScheduleWire) => string;
  pipelineDeliveryHint?: (
    episodeDay: number,
    schedule: ScheduleWire,
  ) => string;
};

async function loadAdvanceModule(): Promise<NextOrderAdvanceModule | null> {
  const hit = CANDIDATE_MODULES.find((p) => existsSync(p));
  if (!hit) return null;
  try {
    return (await import(hit)) as NextOrderAdvanceModule;
  } catch {
    return null;
  }
}

describe("T-086 next-order-day advance helpers (schedule fields only)", () => {
  it("ships a calendar helper module that exports buildStepNOrders", async () => {
    const mod = await loadAdvanceModule();
    expect(
      mod,
      "expected web/src/calendar/nextOrderAdvance.ts (or engine/nextOrderAdvance.ts)",
    ).not.toBeNull();
    expect(typeof mod!.buildStepNOrders).toBe("function");
  });

  it("buildStepNOrders from Monday (day 0) jumps to Tuesday with zero on Mon then order on Tue", async () => {
    const mod = await loadAdvanceModule();
    expect(mod?.buildStepNOrders).toBeTypeOf("function");
    // Day 0 = Mon 2024-01-01; next order day = Tue (1). Length = 1 − 0 = 1.
    const orders = mod!.buildStepNOrders!(0, 16, DEFAULT_SCHEDULE);
    expect(orders).toEqual([0, 16]);
  });

  it("buildStepNOrders zeros intervening non-order days then places qty on target", async () => {
    const mod = await loadAdvanceModule();
    expect(mod?.buildStepNOrders).toBeTypeOf("function");
    // Day 6 = Sun (order day); next order = Tue day 8 → [0 (Mon), 16 (Tue)].
    const orders = mod!.buildStepNOrders!(6, 16, DEFAULT_SCHEDULE);
    expect(orders).toEqual([0, 0, 16]);
    expect(orders.every((q, i) => (i < orders.length - 1 ? q === 0 : q === 16))).toBe(
      true,
    );
  });

  it("buildStepNOrders from Friday lands on Sunday with Fri/Sat zeros then order", async () => {
    const mod = await loadAdvanceModule();
    expect(mod?.buildStepNOrders).toBeTypeOf("function");
    // Day 4 = Fri; next order = Sun day 6 → [0 (Sat), 24 (Sun)].
    const orders = mod!.buildStepNOrders!(4, 24, DEFAULT_SCHEDULE);
    expect(orders).toEqual([0, 0, 24]);
  });

  it("next order day is strictly after current day (never includes today)", async () => {
    const mod = await loadAdvanceModule();
    const nextFn = mod?.nextOrderDayFromSchedule ?? null;
    const build = mod?.buildStepNOrders;
    expect(build ?? nextFn, "need nextOrderDayFromSchedule or buildStepNOrders").toBeTruthy();

    // On an order day (Tue = 1), successor must be Thu = 3, not today.
    if (nextFn) {
      expect(nextFn(1, DEFAULT_SCHEDULE)).toBe(3);
      expect(nextFn(1, DEFAULT_SCHEDULE)).toBeGreaterThan(1);
    }
    if (build) {
      const orders = build(1, 8, DEFAULT_SCHEDULE);
      expect(orders.length).toBe(3 - 1 + 1); // days 1..3 inclusive
      expect(orders[orders.length - 1]).toBe(8);
      expect(orders.slice(0, -1).every((q) => q === 0)).toBe(true);
    }
  });

  it("weekdayLabel derives Mon..Sun from epoch 2024-01-01 + episode day", async () => {
    const mod = await loadAdvanceModule();
    expect(mod?.weekdayLabel).toBeTypeOf("function");
    for (let d = 0; d < 7; d++) {
      const label = mod!.weekdayLabel!(d, DEFAULT_SCHEDULE);
      expect(label).toMatch(new RegExp(WEEKDAY_NAMES[d]!, "i"));
    }
    // Day 7 wraps to Monday again.
    expect(mod!.weekdayLabel!(7, DEFAULT_SCHEDULE)).toMatch(/mon/i);
  });

  it("pipelineDeliveryHint surfaces next-day delivery for LT=1 (order → next day)", async () => {
    const mod = await loadAdvanceModule();
    expect(mod?.pipelineDeliveryHint).toBeTypeOf("function");
    // Ordering on Tue (day 1) → delivery Wed (day 2) under LT=1.
    const hint = mod!.pipelineDeliveryHint!(1, DEFAULT_SCHEDULE);
    expect(hint.length).toBeGreaterThan(0);
    expect(hint).toMatch(/wed|delivery|deliver|arrive|pipeline|LT\s*=?\s*1/i);
  });

  it("helpers consume schedule.order_weekdays / epoch — do not hardcode a second OrderSchedule", () => {
    const hit = CANDIDATE_MODULES.find((p) => existsSync(p));
    expect(
      hit,
      "calendar helper source must exist so ADR 0111 consumption can be reviewed",
    ).toBeTruthy();
    const src = readFileSync(hit!, "utf8");
    // May read order_weekdays from the wire; must not invent protection_days math.
    expect(src).not.toMatch(/protection_days\s*\(/);
    expect(src).toMatch(/order_weekdays|schedule/);
    expect(src).toMatch(/epoch|2024-01-01/);
  });
});

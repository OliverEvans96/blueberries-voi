/**
 * Next-order-day advance helpers for studio chrome (T-086 / CAL-C2).
 * Consumes Snapshot ScheduleWire fields only — no OrderSchedule redefinition
 * (ADR 0111).
 */
import type { ScheduleWire } from "../engine/types";

const WEEKDAY_SHORT = [
  "Mon",
  "Tue",
  "Wed",
  "Thu",
  "Fri",
  "Sat",
  "Sun",
] as const;

/** Monday=0 … Sunday=6 from schedule.epoch + episode day. */
export function weekdayMonday0(
  episodeDay: number,
  schedule: ScheduleWire,
): number {
  const epochIso = schedule.epoch.slice(0, 10);
  const epoch = new Date(`${epochIso}T00:00:00Z`);
  const d = new Date(epoch);
  d.setUTCDate(epoch.getUTCDate() + episodeDay);
  // JS Sunday=0 → monday0
  return (d.getUTCDay() + 6) % 7;
}

/** Smallest d > currentDay with weekday in schedule.order_weekdays. */
export function nextOrderDayFromSchedule(
  currentDay: number,
  schedule: ScheduleWire,
): number {
  const orderSet = new Set(schedule.order_weekdays);
  let d = currentDay + 1;
  // Bound search; weekly cadence guarantees a hit within 7 days.
  for (let i = 0; i < 14; i++) {
    if (orderSet.has(weekdayMonday0(d, schedule))) return d;
    d += 1;
  }
  throw new Error("no next order day within two weeks of schedule.order_weekdays");
}

/**
 * Build step_n orders: zeros on intervening non-order days, qty on the
 * target next order day. Length = next_order_day − current_day.
 */
export function buildStepNOrders(
  currentDay: number,
  orderQty: number,
  schedule: ScheduleWire,
): number[] {
  const target = nextOrderDayFromSchedule(currentDay, schedule);
  const len = target - currentDay;
  const orders = Array.from({ length: len }, () => 0);
  orders[len - 1] = orderQty;
  return orders;
}

/** Weekday label (Mon..Sun) from epoch 2024-01-01 + episode day. */
export function weekdayLabel(
  episodeDay: number,
  schedule: ScheduleWire,
): string {
  return WEEKDAY_SHORT[weekdayMonday0(episodeDay, schedule)]!;
}

/**
 * LT=1 pipeline hint: an order placed on episodeDay arrives the next day.
 */
export function pipelineDeliveryHint(
  episodeDay: number,
  schedule: ScheduleWire,
): string {
  const lt = schedule.lead_time_days;
  const arriveDay = episodeDay + lt;
  const arriveLabel = weekdayLabel(arriveDay, schedule);
  return `Next delivery ${arriveLabel} (order→+${lt} day, LT=${lt})`;
}

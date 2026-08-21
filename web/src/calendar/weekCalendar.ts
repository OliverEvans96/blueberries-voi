/**
 * Week calendar widget — delivery / order weekday chrome (T-140 / ADR 0114).
 * Epoch 2024-01-01 (Monday = 0); order weekdays derived from delivery + lead time.
 */
import { WEEKDAY_LABELS_MONDAY0 } from "../charts/demandDist";
import type { ScheduleWire } from "../engine/types";
import type { SimConfig } from "../types";

export const SCHEDULE_EPOCH = "2024-01-01";

/** Order weekday = delivery weekday minus lead time (monday0 mod 7). */
export function deriveOrderWeekdays(
  deliveryWeekdays: number[],
  leadTimeDays: number,
): number[] {
  const lt = Math.max(0, Math.round(leadTimeDays));
  const orderSet = new Set<number>();
  for (const d of deliveryWeekdays) {
    orderSet.add(((d - lt) % 7 + 7) % 7);
  }
  return [...orderSet].sort((a, b) => a - b);
}

/** Build ScheduleWire from staged SimConfig knobs. */
export function scheduleFromConfig(
  config: Pick<SimConfig, "delivery_weekdays" | "lead_time">,
): ScheduleWire {
  const delivery = [...config.delivery_weekdays].sort((a, b) => a - b);
  const lead = Math.max(0, Math.round(config.lead_time));
  return {
    delivery_weekdays: delivery,
    order_weekdays: deriveOrderWeekdays(delivery, lead),
    lead_time_days: lead,
    epoch: SCHEDULE_EPOCH,
  };
}

/** Toggle one delivery weekday; never returns an empty set. */
export function toggleDeliveryDay(current: number[], weekday: number): number[] {
  const set = new Set(current);
  if (set.has(weekday)) {
    if (set.size <= 1) return [...current].sort((a, b) => a - b);
    set.delete(weekday);
  } else {
    set.add(weekday);
  }
  return [...set].sort((a, b) => a - b);
}

export type WeekCalendarOpts = {
  onToggleDelivery: (weekday: number) => void;
  disabled?: boolean;
};

/** Render seven-day delivery / order calendar into host (replaces children). */
export function renderWeekCalendar(
  host: HTMLElement,
  schedule: ScheduleWire,
  opts: WeekCalendarOpts,
): void {
  host.replaceChildren();
  const deliverySet = new Set(schedule.delivery_weekdays);
  const orderSet = new Set(schedule.order_weekdays);
  const disabled = opts.disabled ?? false;

  for (let wd = 0; wd < 7; wd += 1) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "week-calendar-day";
    btn.dataset.weekday = String(wd);
    const isDelivery = deliverySet.has(wd);
    const isOrder = orderSet.has(wd);
    if (isDelivery && isOrder) btn.classList.add("is-both");
    else if (isDelivery) btn.classList.add("is-delivery");
    else if (isOrder) btn.classList.add("is-order");

    const label = WEEKDAY_LABELS_MONDAY0[wd] ?? `wd${wd}`;
    btn.textContent = label;
    const roles: string[] = [];
    if (isDelivery) roles.push("delivery");
    if (isOrder) roles.push("order");
    btn.title =
      roles.length > 0
        ? `${label}: ${roles.join(" + ")}`
        : `${label}: click to add delivery`;
    btn.setAttribute("aria-pressed", isDelivery ? "true" : "false");
    btn.disabled = disabled;

    if (!disabled) {
      btn.addEventListener("click", () => opts.onToggleDelivery(wd));
    }
    host.appendChild(btn);
  }
}

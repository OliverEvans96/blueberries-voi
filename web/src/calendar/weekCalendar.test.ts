/**
 * T-140: week calendar — order derivation, toggle, render.
 */
// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import {
  deriveOrderWeekdays,
  renderWeekCalendar,
  scheduleFromConfig,
  toggleDeliveryDay,
} from "./weekCalendar";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";

describe("weekCalendar (T-140)", () => {
  it("LT=1 MWF delivery → Sun/Tue/Thu order weekdays", () => {
    expect(deriveOrderWeekdays([0, 2, 4], 1)).toEqual([1, 3, 6]);
    const sched = scheduleFromConfig({
      ...DEFAULT_SIM_CONFIG,
      delivery_weekdays: [0, 2, 4],
      lead_time: 1,
    });
    expect(sched.order_weekdays).toEqual([1, 3, 6]);
    expect(sched.epoch).toBe("2024-01-01");
  });

  it("LT=2 shifts order weekdays forward", () => {
    expect(deriveOrderWeekdays([0, 2, 4], 2)).toEqual([0, 2, 5]);
    const sched = scheduleFromConfig({
      ...DEFAULT_SIM_CONFIG,
      delivery_weekdays: [0, 2, 4],
      lead_time: 2,
    });
    expect(sched.order_weekdays).toEqual([0, 2, 5]);
    expect(sched.lead_time_days).toBe(2);
  });

  it("toggle delivery adds and removes weekdays", () => {
    expect(toggleDeliveryDay([0, 2, 4], 1)).toEqual([0, 1, 2, 4]);
    expect(toggleDeliveryDay([0, 1, 2, 4], 1)).toEqual([0, 2, 4]);
  });

  it("cannot deselect the last delivery day", () => {
    expect(toggleDeliveryDay([3], 3)).toEqual([3]);
  });

  it("renderWeekCalendar marks delivery/order classes and toggles via callback", () => {
    const host = document.createElement("div");
    const onToggle = vi.fn();
    const schedule = scheduleFromConfig({
      ...DEFAULT_SIM_CONFIG,
      delivery_weekdays: [0, 2, 4],
      lead_time: 1,
    });
    renderWeekCalendar(host, schedule, { onToggleDelivery: onToggle });

    const days = host.querySelectorAll(".week-calendar-day");
    expect(days.length).toBe(7);
    expect(host.querySelector(".week-calendar-day.is-delivery[data-weekday='0']")).toBeTruthy();
    expect(host.querySelector(".week-calendar-day.is-order[data-weekday='6']")).toBeTruthy();

    const wed = host.querySelector("[data-weekday='2']") as HTMLButtonElement;
    wed.click();
    expect(onToggle).toHaveBeenCalledWith(2);
  });
});

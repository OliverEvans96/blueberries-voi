/**
 * T-148: week calendar Sunday-first header and grid structure.
 */
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import {
  renderWeekCalendar,
  SUNDAY_FIRST_MONDAY0_ORDER,
  WEEKDAY_HEADERS_SUNDAY_FIRST,
} from "./weekCalendar";
import type { ScheduleWire } from "../engine/types";

const SCHEDULE: ScheduleWire = {
  delivery_weekdays: [0, 2, 4],
  order_weekdays: [5, 1, 3],
  lead_time_days: 2,
  epoch: "2024-01-01",
};

describe("weekCalendar (T-148)", () => {
  it("renders Su-first header row before day buttons", () => {
    const host = document.createElement("div");
    renderWeekCalendar(host, SCHEDULE, { onToggleDelivery: () => undefined });

    const header = host.querySelector(".week-calendar-header");
    expect(header).not.toBeNull();
    const labels = [...header!.querySelectorAll(".week-calendar-header-cell")].map(
      (el) => el.textContent,
    );
    expect(labels).toEqual([...WEEKDAY_HEADERS_SUNDAY_FIRST]);
  });

  it("orders day buttons in Sunday-first monday0 sequence", () => {
    const host = document.createElement("div");
    renderWeekCalendar(host, SCHEDULE, { onToggleDelivery: () => undefined });
    const grid = host.querySelector(".week-calendar-grid");
    const weekdays = [...grid!.querySelectorAll(".week-calendar-day")].map((el) =>
      Number(el.dataset.weekday),
    );
    expect(weekdays).toEqual([...SUNDAY_FIRST_MONDAY0_ORDER]);
  });
});

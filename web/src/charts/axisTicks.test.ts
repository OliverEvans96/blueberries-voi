import { describe, expect, it } from "vitest";
import { MIN_CHART_DAY_SPAN, padDaysToMinRange, pickDayTicks } from "./axisTicks";

describe("padDaysToMinRange", () => {
  it("extends short real history forward to minDays consecutive slots", () => {
    expect(padDaysToMinRange([1, 2], 5)).toEqual([1, 2, 3, 4, 5]);
  });

  it("seeds day 0..4 when history is empty", () => {
    expect(padDaysToMinRange([], 5)).toEqual([0, 1, 2, 3, 4]);
  });

  it("leaves domain unchanged when real span already meets minDays", () => {
    expect(padDaysToMinRange([1, 2, 3, 4, 5, 6, 7], 5)).toEqual([
      1, 2, 3, 4, 5, 6, 7,
    ]);
  });

  it("defaults minDays to MIN_CHART_DAY_SPAN", () => {
    expect(padDaysToMinRange([0, 1])).toEqual([0, 1, 2, 3, 4]);
    expect(MIN_CHART_DAY_SPAN).toBe(5);
  });
});

describe("pickDayTicks", () => {
  it("keeps every day when they all fit comfortably", () => {
    const days = [0, 1, 2, 3, 4, 5];
    expect(pickDayTicks(days, 600)).toEqual(days);
  });

  it("thins ticks further as episode length grows for a fixed width", () => {
    const width = 300;
    const short = [...Array(10).keys()];
    const long = [...Array(90).keys()];
    const shortTicks = pickDayTicks(short, width);
    const longTicks = pickDayTicks(long, width);
    // longer episode at the same width must not render more labels than the shorter one
    expect(longTicks.length).toBeLessThanOrEqual(shortTicks.length);
  });

  it("never packs ticks closer than the minimum pixel budget", () => {
    const days = [...Array(200).keys()];
    const innerWidthPx = 640;
    const picked = pickDayTicks(days, innerWidthPx);
    const pxPerDay = innerWidthPx / days.length;
    for (let i = 1; i < picked.length; i++) {
      const spacingPx = (picked[i]! - picked[i - 1]!) * pxPerDay;
      expect(spacingPx).toBeGreaterThanOrEqual(28 - 1e-9);
    }
  });

  it("always keeps the last day so the axis doesn't lose its right edge", () => {
    const days = [...Array(137).keys()];
    const picked = pickDayTicks(days, 500);
    expect(picked[picked.length - 1]).toBe(days[days.length - 1]);
  });

  it("returns all days unchanged for 0 or 1 days", () => {
    expect(pickDayTicks([], 400)).toEqual([]);
    expect(pickDayTicks([5], 400)).toEqual([5]);
  });
});

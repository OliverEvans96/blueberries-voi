import { describe, expect, it } from "vitest";
import {
  formatTempC,
  lotColor,
  LOT_COLORS,
  tempSummaryFromTrace,
  tracesFromEvent,
} from "./deliveryTempChart";

describe("tracesFromEvent", () => {
  it("prefers temp_traces_by_lot when present", () => {
    const traces = tracesFromEvent({
      arrivals: 8,
      temp_traces_by_lot: [
        {
          lot_id: 301,
          times_d: [-2, -1, 0],
          temps_c: [2, 2.2, 2.4],
        },
        {
          lot_id: 302,
          times_d: [-2, -1, 0],
          temps_c: [2.5, 2.7, 2.9],
        },
      ],
    });
    expect(traces).toEqual([
      { lotId: 301, times_d: [-2, -1, 0], temps_c: [2, 2.2, 2.4] },
      { lotId: 302, times_d: [-2, -1, 0], temps_c: [2.5, 2.7, 2.9] },
    ]);
  });

  it("falls back to legacy temp_times_d / temp_temps_c", () => {
    const traces = tracesFromEvent({
      arrivals: 8,
      arrival_lot_ids: [401],
      temp_times_d: [-3, -2, -1, 0],
      temp_temps_c: [2, 2.2, 2.4, 2.6],
    });
    expect(traces).toEqual([
      {
        lotId: 401,
        times_d: [-3, -2, -1, 0],
        temps_c: [2, 2.2, 2.4, 2.6],
      },
    ]);
  });

  it("returns an empty array when no temperature data exists", () => {
    expect(tracesFromEvent({ arrivals: 4 })).toEqual([]);
  });
});

describe("tempSummaryFromTrace", () => {
  it("computes min / max / mean / std from finite temps", () => {
    const summary = tempSummaryFromTrace({
      lotId: 301,
      times_d: [-3, -2, -1, 0],
      temps_c: [2, 2.2, 2.4, 2.6],
    });
    expect(summary).toEqual({
      min: 2,
      max: 2.6,
      mean: 2.3,
      std: expect.closeTo(0.2582, 4),
      n: 4,
    });
  });

  it("uses zero std when fewer than two finite temps", () => {
    const summary = tempSummaryFromTrace({
      lotId: 1,
      times_d: [0],
      temps_c: [2.5],
    });
    expect(summary).toEqual({
      min: 2.5,
      max: 2.5,
      mean: 2.5,
      std: 0,
      n: 1,
    });
  });

  it("returns null when no finite temps exist", () => {
    expect(
      tempSummaryFromTrace({
        lotId: 1,
        times_d: [0],
        temps_c: [Number.NaN],
      }),
    ).toBeNull();
  });
});

describe("formatTempC", () => {
  it("formats one decimal place with a degree symbol", () => {
    expect(formatTempC(2.34)).toBe("2.3°C");
  });
});

describe("lotColor", () => {
  it("cycles through LOT_COLORS", () => {
    expect(lotColor(0)).toBe(LOT_COLORS[0]);
    expect(lotColor(LOT_COLORS.length)).toBe(LOT_COLORS[0]);
  });
});

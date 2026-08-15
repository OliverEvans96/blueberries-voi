/**
 * T-115 RED: inventory vs target and age composition from belief vs truth lots.
 */
import { describe, expect, it } from "vitest";
import type { FlatBelief } from "../engine/types";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";
import type { Day } from "../types";
import * as inv from "./inventoryTarget";
import { inventorySeries } from "./inventoryTarget";

type BeliefDay = { day: number; flatBelief: FlatBelief };

type InventoryOpts = {
  from: "lots" | "belief";
  belief_history?: BeliefDay[];
};

type AgeRow = { day: number; young: number; mid: number; old: number };

const LOT_DAY: Day = {
  day: 0,
  lots: [
    { lot_id: 1, n: 10, tau: 1 },
    { lot_id: 2, n: 5, tau: 4 },
    { lot_id: 3, n: 3, tau: 7 },
  ],
  sales_total: 0,
  waste_total: 0,
  demand: 0,
  order_qty: 0,
  arrivals: 0,
  stockout: 0,
  age_at_receipt: null,
};

/** Expected on-hand from belief is Σ lot_counts (6.92), not truth lot n (18). */
const FLAT: FlatBelief = {
  L: 2,
  K: 3,
  lot_counts: [3.6, 3.32],
  age_marginals: [1, 0, 0, 0, 0, 1],
  tau_grid: [1, 4, 7],
};

const BELIEF_HISTORY: BeliefDay[] = [{ day: 0, flatBelief: FLAT }];

describe("inventorySeries lots vs belief (T-115)", () => {
  it("truth lots path: on_hand equals sum of lot n", () => {
    const series = inventorySeries([LOT_DAY], DEFAULT_SIM_CONFIG);
    expect(series[0]!.on_hand).toBe(18);
  });

  it("belief path: on_hand equals Σ lot_counts for that day, not the truth lot sum", () => {
    const fn = (
      inv as {
        inventorySeriesFromBelief?: (
          beliefHistory: BeliefDay[],
          config: typeof DEFAULT_SIM_CONFIG,
        ) => Array<{ day: number; on_hand: number; effective: number }>;
        inventorySeries?: (
          history: Day[],
          config: typeof DEFAULT_SIM_CONFIG,
          opts?: InventoryOpts,
        ) => Array<{ day: number; on_hand: number; effective: number }>;
      }
    ).inventorySeriesFromBelief;
    const seriesFn = (
      inv as {
        inventorySeries: (
          history: Day[],
          config: typeof DEFAULT_SIM_CONFIG,
          opts?: InventoryOpts,
        ) => Array<{ day: number; on_hand: number; effective: number }>;
      }
    ).inventorySeries;

    let series: Array<{ day: number; on_hand: number }>;
    if (typeof fn === "function") {
      series = fn(BELIEF_HISTORY, DEFAULT_SIM_CONFIG);
    } else {
      series = seriesFn([LOT_DAY], DEFAULT_SIM_CONFIG, {
        from: "belief",
        belief_history: BELIEF_HISTORY,
      });
    }
    const expected = FLAT.lot_counts.reduce((s, n) => s + n, 0);
    expect(series).toHaveLength(1);
    expect(series[0]!.on_hand).toBeCloseTo(expected);
    expect(series[0]!.on_hand).not.toBe(18);
  });
});

describe("age composition lots vs belief (T-115)", () => {
  it("truth lots path: 0–2 / 3–5 / 6d+ bands from lot tau and n", () => {
    const fn = (
      inv as {
        ageCompositionSeries?: (
          history: Day[],
          opts?: InventoryOpts,
        ) => AgeRow[];
      }
    ).ageCompositionSeries;
    expect(typeof fn, "expected ageCompositionSeries export").toBe("function");
    const rows = fn!([LOT_DAY]);
    expect(rows[0]).toEqual({ day: 0, young: 10, mid: 5, old: 3 });
  });

  it("belief path: bands from expected ages, not truth lots", () => {
    const fn = (
      inv as {
        ageCompositionSeries?: (
          history: Day[],
          opts?: InventoryOpts,
        ) => AgeRow[];
        ageCompositionSeriesFromBelief?: (beliefHistory: BeliefDay[]) => AgeRow[];
      }
    ).ageCompositionSeriesFromBelief;
    const seriesFn = (
      inv as {
        ageCompositionSeries?: (
          history: Day[],
          opts?: InventoryOpts,
        ) => AgeRow[];
      }
    ).ageCompositionSeries;

    let rows: AgeRow[];
    if (typeof fn === "function") {
      rows = fn(BELIEF_HISTORY);
    } else {
      expect(typeof seriesFn).toBe("function");
      rows = seriesFn!([LOT_DAY], {
        from: "belief",
        belief_history: BELIEF_HISTORY,
      });
    }
    // lot 0: all mass at tau=1 (young); lot 1: all mass at tau=7 (old)
    expect(rows[0]!.young).toBeCloseTo(3.6);
    expect(rows[0]!.mid).toBeCloseTo(0);
    expect(rows[0]!.old).toBeCloseTo(3.32);
    expect(rows[0]!.young + rows[0]!.mid + rows[0]!.old).not.toBe(18);
  });
});

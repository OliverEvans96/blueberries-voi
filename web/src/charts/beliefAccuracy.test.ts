/**
 * Belief pane shelf mean-f MAE helpers.
 */
import { describe, expect, it } from "vitest";
import type { FlatBelief } from "../engine/types";
import type { BeliefHistoryDay, Day, Unit } from "../types";
import {
  BELIEF_MAE_DECIMALS,
  currentMeanFAbsError,
  formatMeanFAbsError,
  meanFreshnessAbsError,
  meanMeanFAbsErrorOverHistory,
  shelfMeanFFromFlat,
  shelfMeanFFromUnits,
} from "./beliefAccuracy";

const FLAT: FlatBelief = {
  L: 3,
  K: 4,
  lot_counts: [10, 6, 4],
  f_grid: [0.125, 0.375, 0.625, 0.875],
  f_marginals: [
    1, 0, 0, 0,
    0, 1, 0, 0,
    0, 0, 1, 0,
  ],
};

const UNITS: Unit[] = Array.from({ length: 10 }, (_, unit_id) => ({
  unit_id,
  lot_id: 1,
  f: 0.3,
}));

function dayRow(day: number, units: Unit[]): Day {
  return {
    day,
    lots: [],
    units,
    sales_total: 0,
    waste_total: 0,
    demand: 0,
    order_qty: 0,
    arrivals: 0,
    stockout: 0,
    f_at_receipt: null,
  };
}

describe("shelfMeanFFromFlat", () => {
  it("matches count-weighted E[f|lot] marginal means", () => {
    const mean = shelfMeanFFromFlat(FLAT);
    expect(mean).not.toBeNull();
    // (10*0.125 + 6*0.375 + 4*0.625) / 20 = 0.3
    expect(mean!).toBeCloseTo(0.3);
  });

  it("returns null when total lot count is zero", () => {
    expect(
      shelfMeanFFromFlat({ ...FLAT, lot_counts: [0, 0, 0] }),
    ).toBeNull();
  });
});

describe("shelfMeanFFromUnits", () => {
  it("averages unit freshness values", () => {
    const units: Unit[] = [
      { unit_id: 0, lot_id: 1, f: 0.2 },
      { unit_id: 1, lot_id: 1, f: 0.4 },
    ];
    expect(shelfMeanFFromUnits(units)).toBeCloseTo(0.3);
  });

  it("returns null for empty units", () => {
    expect(shelfMeanFFromUnits([])).toBeNull();
  });
});

describe("meanFreshnessAbsError", () => {
  it("returns absolute difference", () => {
    expect(meanFreshnessAbsError(0.4, 0.325)).toBeCloseTo(0.075);
  });
});

describe("currentMeanFAbsError", () => {
  it("is zero when belief and truth shelf means agree", () => {
    expect(currentMeanFAbsError(FLAT, UNITS)).toBeCloseTo(0);
  });

  it("returns null when units are empty", () => {
    expect(currentMeanFAbsError(FLAT, [])).toBeNull();
  });
});

describe("meanMeanFAbsErrorOverHistory", () => {
  it("averages per-day MAE over aligned history rows", () => {
    const history: Day[] = [
      dayRow(0, UNITS.slice(0, 5)),
      dayRow(1, UNITS),
    ];
    const beliefHistory: BeliefHistoryDay[] = [
      { day: 0, flatBelief: FLAT },
      { day: 1, flatBelief: FLAT },
    ];
    const result = meanMeanFAbsErrorOverHistory(history, beliefHistory);
    expect(result).not.toBeNull();
    expect(result!.dayCount).toBe(2);
    expect(result!.meanMae).toBeCloseTo(0);
  });

  it("skips days without matching belief or truth units", () => {
    const history: Day[] = [dayRow(0, []), dayRow(1, UNITS)];
    const beliefHistory: BeliefHistoryDay[] = [{ day: 1, flatBelief: FLAT }];
    const result = meanMeanFAbsErrorOverHistory(history, beliefHistory);
    expect(result).not.toBeNull();
    expect(result!.dayCount).toBe(1);
  });

  it("returns null when no valid aligned days", () => {
    expect(meanMeanFAbsErrorOverHistory([], [])).toBeNull();
    expect(
      meanMeanFAbsErrorOverHistory([dayRow(0, [])], [{ day: 0, flatBelief: FLAT }]),
    ).toBeNull();
  });
});

describe("formatMeanFAbsError", () => {
  it(`uses ${BELIEF_MAE_DECIMALS} decimal places`, () => {
    expect(formatMeanFAbsError(0.04167)).toBe("0.042");
    expect(formatMeanFAbsError(0.1)).toBe("0.100");
  });
});

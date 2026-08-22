/**
 * T-148: cumulative missed sales and waste totals from episode history.
 */
import { describe, expect, it } from "vitest";
import { computeImpactTotals } from "./impactTotals";

describe("computeImpactTotals", () => {
  it("sums missed sales and waste with denominator percentages", () => {
    const history = [
      {
        day: 1,
        lots: [],
        sales_total: 8,
        waste_total: 1,
        demand: 10,
        order_qty: 24,
        arrivals: 16,
        stockout: 2,
        f_at_receipt: null,
      },
      {
        day: 2,
        lots: [],
        sales_total: 6,
        waste_total: 2,
        demand: 8,
        order_qty: 0,
        arrivals: 0,
        stockout: 2,
        f_at_receipt: null,
      },
    ];

    const t = computeImpactTotals(history);
    expect(t.missedTotal).toBe(4);
    expect(t.cumulativeDemand).toBe(18);
    expect(t.missedPct).toBeCloseTo(4 / 18);
    expect(t.wasteTotal).toBe(3);
    expect(t.cumulativeOrderQty).toBe(24);
    expect(t.wastePct).toBeCloseTo(3 / 24);
  });

  it("returns zero percentages when denominators are empty", () => {
    const t = computeImpactTotals([]);
    expect(t.missedTotal).toBe(0);
    expect(t.wasteTotal).toBe(0);
    expect(t.missedPct).toBe(0);
    expect(t.wastePct).toBe(0);
  });
});

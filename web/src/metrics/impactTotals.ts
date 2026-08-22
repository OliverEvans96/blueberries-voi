import type { Day } from "../types";

export type ImpactTotals = {
  missedTotal: number;
  missedPct: number;
  wasteTotal: number;
  wastePct: number;
  cumulativeDemand: number;
  cumulativeOrderQty: number;
};

/** Cumulative missed sales and waste with denominator percentages from episode history. */
export function computeImpactTotals(history: readonly Day[]): ImpactTotals {
  let cumulativeDemand = 0;
  let missedTotal = 0;
  let cumulativeOrderQty = 0;
  let wasteTotal = 0;

  for (const d of history) {
    cumulativeDemand += d.demand;
    missedTotal += d.stockout;
    cumulativeOrderQty += d.order_qty;
    wasteTotal += d.waste_total;
  }

  return {
    missedTotal,
    missedPct: cumulativeDemand > 0 ? missedTotal / cumulativeDemand : 0,
    wasteTotal,
    wastePct: cumulativeOrderQty > 0 ? wasteTotal / cumulativeOrderQty : 0,
    cumulativeDemand,
    cumulativeOrderQty,
  };
}

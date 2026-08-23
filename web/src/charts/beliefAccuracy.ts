import type { FlatBelief } from "../engine/types";
import type { BeliefHistoryDay, Day, Unit } from "../types";

/** Tooltip / title copy for shelf mean-f MAE stats. */
export const BELIEF_MAE_DEFINITION =
  "Mean absolute error between belief and truth shelf-mean freshness f: " +
  "|Σ_l lot_counts[l]·E[f|l] / Σ_l lot_counts[l] − Σ unit.f / N|.";

export const BELIEF_MAE_DECIMALS = 3;

/** Format a mean-f absolute error for display (three decimal places). */
export function formatMeanFAbsError(value: number): string {
  return value.toFixed(BELIEF_MAE_DECIMALS);
}

/** Belief shelf mean: Σ_l lot_counts[l] × E[f|lot l] / Σ_l lot_counts[l]. */
export function shelfMeanFFromFlat(flat: FlatBelief): number | null {
  const { L, K, lot_counts, f_marginals, f_grid } = flat;
  let total = 0;
  for (let l = 0; l < L; l++) {
    total += lot_counts[l] ?? 0;
  }
  if (total <= 0) {
    return null;
  }
  let weighted = 0;
  for (let l = 0; l < L; l++) {
    const count = lot_counts[l] ?? 0;
    if (count <= 0) continue;
    let eF = 0;
    for (let k = 0; k < K; k++) {
      eF += (f_marginals[l * K + k] ?? 0) * (f_grid[k] ?? 0);
    }
    weighted += count * eF;
  }
  return weighted / total;
}

/** Truth shelf mean: Σ unit.f / N. */
export function shelfMeanFFromUnits(units: readonly Unit[]): number | null {
  if (units.length <= 0) {
    return null;
  }
  let sum = 0;
  for (const unit of units) {
    sum += unit.f;
  }
  return sum / units.length;
}

/** Absolute error between belief and truth shelf mean f. */
export function meanFreshnessAbsError(beliefF: number, truthF: number): number {
  return Math.abs(beliefF - truthF);
}

/** Current-day MAE from a flat belief vs live truth units. */
export function currentMeanFAbsError(
  flat: FlatBelief,
  units: readonly Unit[],
): number | null {
  const beliefF = shelfMeanFFromFlat(flat);
  const truthF = shelfMeanFFromUnits(units);
  if (beliefF == null || truthF == null) {
    return null;
  }
  return meanFreshnessAbsError(beliefF, truthF);
}

export type MeanMaeOverHistory = {
  meanMae: number;
  dayCount: number;
};

function beliefByDay(
  beliefHistory: readonly BeliefHistoryDay[],
): Map<number, FlatBelief> {
  const map = new Map<number, FlatBelief>();
  for (const row of beliefHistory) {
    map.set(row.day, row.flatBelief);
  }
  return map;
}

/**
 * Mean daily MAE over history days aligned with `belief_history`.
 * Skips days with no truth units or zero on-hand.
 */
export function meanMeanFAbsErrorOverHistory(
  history: readonly Day[],
  beliefHistory: readonly BeliefHistoryDay[],
): MeanMaeOverHistory | null {
  if (history.length === 0 || beliefHistory.length === 0) {
    return null;
  }
  const beliefs = beliefByDay(beliefHistory);
  const errors: number[] = [];
  for (const dayRow of history) {
    const flat = beliefs.get(dayRow.day);
    const units = dayRow.units ?? [];
    if (!flat || units.length === 0) {
      continue;
    }
    const mae = currentMeanFAbsError(flat, units);
    if (mae != null) {
      errors.push(mae);
    }
  }
  if (errors.length === 0) {
    return null;
  }
  const sum = errors.reduce((acc, v) => acc + v, 0);
  return { meanMae: sum / errors.length, dayCount: errors.length };
}

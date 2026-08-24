import { centersToEdges } from "../engine/projector";
import type { FlatBelief } from "../engine/types";
import type { BeliefHistoryDay, Day, Unit } from "../types";
import {
  aggregateBeliefMasses,
  DISPLAY_BIN_COUNT,
  histogramEdges,
  rebinMassesByInterval,
  truthMassesFromUnits,
} from "./freshnessHistogram";

/** Tooltip / title copy for shelf mean-f MAE stats. */
export const BELIEF_MAE_DEFINITION =
  "Mean absolute error between belief and truth shelf-mean freshness f: " +
  "|Σ_l lot_counts[l]·E[f|l] / Σ_l lot_counts[l] − Σ unit.f / N|.";

/** Tooltip copy for distribution MAE on display bins. */
export const BELIEF_DIST_MAE_DEFINITION =
  "Mean absolute error between normalized belief and truth unit-count " +
  "distributions on 8 display bins over [0,1]: (1/K) Σ_k |p_k − q_k|.";

/** Combined tooltip for belief-pane MAE stat rows. */
export const BELIEF_MAE_TOOLTIP =
  `${BELIEF_MAE_DEFINITION} ${BELIEF_DIST_MAE_DEFINITION}`;

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

/** Display-bin masses for a flat belief and live truth units (8 bins on [0, 1]). */
export function displayBinMassesForFlatAndUnits(
  flat: FlatBelief,
  units: readonly Unit[],
): { belief: number[]; truth: number[] } {
  const f_edges = centersToEdges(flat.f_grid);
  const belief_masses = aggregateBeliefMasses(flat);
  const edges = histogramEdges(0, 1, DISPLAY_BIN_COUNT);
  const belief = rebinMassesByInterval(f_edges, belief_masses, edges);
  const truth = truthMassesFromUnits(units, edges);
  return { belief, truth };
}

/**
 * Distribution MAE between normalized belief and truth masses on K bins:
 * (1/K) Σ_k |p_k − q_k| where p and q are unit-count shares per bin.
 */
export function distributionAbsError(
  beliefMasses: readonly number[],
  truthMasses: readonly number[],
): number | null {
  const beliefTotal = beliefMasses.reduce((acc, mass) => acc + mass, 0);
  const truthTotal = truthMasses.reduce((acc, mass) => acc + mass, 0);
  if (beliefTotal <= 0 || truthTotal <= 0) {
    return null;
  }
  const k = beliefMasses.length;
  if (k === 0 || truthMasses.length !== k) {
    return null;
  }
  let sum = 0;
  for (let i = 0; i < k; i++) {
    const p = (beliefMasses[i] ?? 0) / beliefTotal;
    const q = (truthMasses[i] ?? 0) / truthTotal;
    sum += Math.abs(p - q);
  }
  return sum / k;
}

/** Current-day distribution MAE from flat belief vs live truth units. */
export function currentDistributionAbsError(
  flat: FlatBelief,
  units: readonly Unit[],
): number | null {
  if (units.length === 0) {
    return null;
  }
  const { belief, truth } = displayBinMassesForFlatAndUnits(flat, units);
  return distributionAbsError(belief, truth);
}

export type MeanDistMaeOverHistory = {
  meanMae: number;
  dayCount: number;
};

/** Mean daily distribution MAE over history days aligned with `belief_history`. */
export function meanDistributionAbsErrorOverHistory(
  history: readonly Day[],
  beliefHistory: readonly BeliefHistoryDay[],
): MeanDistMaeOverHistory | null {
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
    const mae = currentDistributionAbsError(flat, units);
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

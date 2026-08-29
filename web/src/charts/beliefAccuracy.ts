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

/**
 * Tooltip copy for freshness-distribution W₁ (1-Wasserstein) on display bins.
 * All-days is the mean of per-day W₁, not a pooled episode-cloud W₁.
 */
export const BELIEF_DIST_W1_DEFINITION =
  "1-Wasserstein distance (W₁) between normalized belief and truth live-unit " +
  "freshness distributions on 8 display bins over [0,1]: ∫|F−G|. " +
  "All-days reports the mean of per-day W₁ (W̄₁), not a single pooled W₁ " +
  "over the episode.";

/** @deprecated Prefer BELIEF_DIST_W1_DEFINITION; kept for older call sites. */
export const BELIEF_DIST_MAE_DEFINITION = BELIEF_DIST_W1_DEFINITION;

/** Combined tooltip for belief-pane accuracy stat rows. */
export const BELIEF_MAE_TOOLTIP =
  `${BELIEF_MAE_DEFINITION} ${BELIEF_DIST_W1_DEFINITION}`;

/**
 * Count accuracy on the studio wire: MAE of E[N] only.
 * Full particle predictive CRPS is not available from FlatBelief (lot_counts
 * are already particle-averaged expectations).
 */
export const BELIEF_COUNT_MAE_DEFINITION =
  "Absolute error |Σ_l lot_counts[l] − N_truth| between expected on-hand " +
  "count (wire lot_counts) and truth live-unit count. CRPS of the particle " +
  "predictive for N is not available on the studio belief wire — only E[N] " +
  "is exported.";

export const BELIEF_MAE_DECIMALS = 3;

/** Format a mean-f absolute error or W₁ for display (three decimal places). */
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

/** Expected on-hand count from wire lot_counts: Σ_l lot_counts[l]. */
export function expectedCountFromFlat(flat: FlatBelief): number {
  let total = 0;
  for (const count of flat.lot_counts) {
    total += count ?? 0;
  }
  return total;
}

/** MAE of E[N] vs truth live-unit count (wire limitation; not CRPS). */
export function countMeanAbsError(
  flat: FlatBelief,
  units: readonly Unit[],
): number | null {
  if (units.length <= 0) {
    return null;
  }
  return Math.abs(expectedCountFromFlat(flat) - units.length);
}

/** Display-bin masses for a flat belief and live truth units (8 bins on [0, 1]). */
export function displayBinMassesForFlatAndUnits(
  flat: FlatBelief,
  units: readonly Unit[],
): { belief: number[]; truth: number[]; edges: number[] } {
  const f_edges = centersToEdges(flat.f_grid);
  const belief_masses = aggregateBeliefMasses(flat);
  const edges = histogramEdges(0, 1, DISPLAY_BIN_COUNT);
  const belief = rebinMassesByInterval(f_edges, belief_masses, edges);
  const truth = truthMassesFromUnits(units, edges);
  return { belief, truth, edges };
}

/**
 * 1-Wasserstein distance between two discrete distributions on shared bin
 * edges: ∫|F−G|. Mass is treated as arriving at the left of each bin, so the
 * CDF is constant on [e_i, e_{i+1}) after including bin i's mass:
 * W₁ = Σ_{i=0}^{K-2} |F_i − G_i| · (e_{i+1} − e_i) with F_i = Σ_{j≤i} p_j.
 * (The final bin contributes 0 because F_{K-1} = G_{K-1} = 1.)
 */
export function wasserstein1FromBinMasses(
  beliefMasses: readonly number[],
  truthMasses: readonly number[],
  edges: readonly number[],
): number | null {
  const beliefTotal = beliefMasses.reduce((acc, mass) => acc + mass, 0);
  const truthTotal = truthMasses.reduce((acc, mass) => acc + mass, 0);
  if (beliefTotal <= 0 || truthTotal <= 0) {
    return null;
  }
  const k = beliefMasses.length;
  if (k === 0 || truthMasses.length !== k || edges.length !== k + 1) {
    return null;
  }
  let cdfP = 0;
  let cdfQ = 0;
  let w1 = 0;
  for (let i = 0; i < k - 1; i++) {
    cdfP += (beliefMasses[i] ?? 0) / beliefTotal;
    cdfQ += (truthMasses[i] ?? 0) / truthTotal;
    const width = (edges[i + 1] ?? 0) - (edges[i] ?? 0);
    if (width > 0) {
      w1 += Math.abs(cdfP - cdfQ) * width;
    }
  }
  return w1;
}

/**
 * @deprecated Use wasserstein1FromBinMasses. Legacy bin MAE retained for
 * notebook/Python parity callers that still import the old name.
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

/** Current-day freshness-distribution W₁ from flat belief vs live truth units. */
export function currentFreshnessW1(
  flat: FlatBelief,
  units: readonly Unit[],
): number | null {
  if (units.length === 0) {
    return null;
  }
  const { belief, truth, edges } = displayBinMassesForFlatAndUnits(flat, units);
  return wasserstein1FromBinMasses(belief, truth, edges);
}

/** @deprecated Prefer currentFreshnessW1. */
export function currentDistributionAbsError(
  flat: FlatBelief,
  units: readonly Unit[],
): number | null {
  return currentFreshnessW1(flat, units);
}

export type MeanW1OverHistory = {
  /** Mean of per-day W₁ (W̄₁), not pooled episode-cloud W₁. */
  meanW1: number;
  dayCount: number;
};

/** @deprecated Prefer MeanW1OverHistory.meanW1. */
export type MeanDistMaeOverHistory = {
  meanMae: number;
  dayCount: number;
};

/**
 * Mean daily freshness-distribution W₁ over history days aligned with
 * `belief_history`. All-days = (1/D) Σ_d W₁(d), never a pooled cloud W₁.
 */
export function meanFreshnessW1OverHistory(
  history: readonly Day[],
  beliefHistory: readonly BeliefHistoryDay[],
): MeanW1OverHistory | null {
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
    const w1 = currentFreshnessW1(flat, units);
    if (w1 != null) {
      errors.push(w1);
    }
  }
  if (errors.length === 0) {
    return null;
  }
  const sum = errors.reduce((acc, v) => acc + v, 0);
  return { meanW1: sum / errors.length, dayCount: errors.length };
}

/**
 * @deprecated Prefer meanFreshnessW1OverHistory. Returns meanMae alias of meanW1
 * for older call sites.
 */
export function meanDistributionAbsErrorOverHistory(
  history: readonly Day[],
  beliefHistory: readonly BeliefHistoryDay[],
): MeanDistMaeOverHistory | null {
  const result = meanFreshnessW1OverHistory(history, beliefHistory);
  if (!result) {
    return null;
  }
  return { meanMae: result.meanW1, dayCount: result.dayCount };
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

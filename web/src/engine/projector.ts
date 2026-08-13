/**
 * ViewModelProjector — RED stub for T-054.
 * Implementer: apply Snapshot/DayDelta into existing ViewModel; own economics locally.
 */

import type { Economics, ViewModel } from "../types";
import type { DayDelta, Snapshot } from "./types";

export type ProjectorOptions = {
  economics?: Economics;
  window_days?: number;
};

/**
 * Builds the D3 ViewModel from engine payloads. setEconomics must never call an
 * EngineAdapter method (local reproject only).
 */
export class ViewModelProjector {
  constructor(_opts?: ProjectorOptions) {
    /* implementer fills state */
  }

  applySnapshot(_snapshot: Snapshot): ViewModel {
    // Stub: incomplete so RED tests fail on observable ViewModel fields.
    return {} as ViewModel;
  }

  applyDelta(_delta: DayDelta): ViewModel {
    return {} as ViewModel;
  }

  /** Local-only: update PnL / ghost from stored history; no engine round-trip. */
  setEconomics(_economics: Partial<Economics>): ViewModel {
    return {} as ViewModel;
  }

  /** Current projected ViewModel (after last apply / setEconomics). */
  getViewModel(): ViewModel {
    return {} as ViewModel;
  }
}

/**
 * Nested heatmap density from flat belief: density[l][k] = lot_counts[l] *
 * age_marginals[l*K + k] (ADR 0098 — JS-only).
 */
export function densityFromFlatBelief(_belief: {
  L: number;
  K: number;
  lot_counts: number[];
  age_marginals: number[];
}): number[][] {
  return [];
}

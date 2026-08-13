/** Wire + adapter types for Snapshot / DayDelta (ADR 0098 / T-053 / T-054). */

import type { Day, Economics, Lot, PipelineOrder, SimConfig } from "../types";

/** Flat belief buffer on the wire (no nested density). */
export type FlatBelief = {
  L: number;
  K: number;
  lot_counts: number[];
  /** Row-major length L*K. */
  age_marginals: number[];
  tau_grid: number[];
};

/** Cold payload from init / reset. */
export type Snapshot = {
  seq: number;
  episode_day: number;
  belief: FlatBelief;
  history?: Day[];
  live_lots?: Lot[];
  pipeline?: PipelineOrder[];
  applied_config?: Partial<SimConfig> & Record<string, unknown>;
};

/** Hot payload from step / step_n / act. */
export type DayDelta = {
  seq: number;
  episode_day: number;
  day: Day | (Partial<Day> & { day: number } & Record<string, unknown>);
  drop_oldest: boolean;
  belief?: FlatBelief | null;
  live_lots?: Lot[];
  pipeline?: Array<PipelineOrder | { qty: number; arrival_day: number }>;
};

/** Presentation keys that must never appear on engine payloads (ADR 0098). */
export const FORBIDDEN_ENGINE_KEYS = [
  "economics",
  "pnl_series",
  "pnl_totals",
  "ghost",
  "ghost_deltas",
  "heatmap",
  "density",
  "ViewModel",
  "view_model",
] as const;

export type ForbiddenEngineKey = (typeof FORBIDDEN_ENGINE_KEYS)[number];

export type EngineConfig = Partial<SimConfig> & Record<string, unknown>;

export type ActOpts = Record<string, unknown>;

export type { Economics };

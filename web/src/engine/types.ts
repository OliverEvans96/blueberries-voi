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

/** Policy aliases locked in ADR 0112. */
export type ActPolicyName =
  | "damped_sw"
  | "sw"
  | "rollout"
  | "ctl"
  | "rollout_order"
  | "constant"
  | "const"
  | "fixed";

/** Budget / knob fields passed through act (ADR 0112). */
export type ActBudgets = {
  alpha?: number;
  rho?: number;
  H?: number;
  n_rollout_paths?: number;
  candidate_case_radius?: number;
  n_particles?: number;
  order_qty?: number;
  q?: number;
};

/**
 * Caller-facing act opts. Nested `budgets` and/or flat top-level knobs are OK;
 * adapters fold via the shared normalizer (HTTP nest / Pyodide flat).
 */
export type ActOpts = {
  policy?: ActPolicyName | string;
  budgets?: ActBudgets;
} & ActBudgets;

export type { Economics };

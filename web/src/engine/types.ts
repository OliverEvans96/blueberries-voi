/** Wire + adapter types for Snapshot / DayDelta (ADR 0098 / T-053 / T-054). */

import type { Day, Economics, Lot, PipelineOrder, SimConfig, Unit } from "../types";

/** Flat belief buffer on the wire (no nested density). */
export type FlatBelief = {
  L: number;
  K: number;
  lot_counts: number[];
  /** Row-major length L*K alive-only normalized marginals. */
  f_marginals: number[];
  /** Freshness bin centers in [0, 1]. */
  f_grid: number[];
};

/** OrderSchedule export for Studio calendar chrome (T-085 / CAL-C1). */
export type ScheduleWire = {
  delivery_weekdays: number[];
  order_weekdays: number[];
  lead_time_days: number;
  /** ISO date for day-index → weekday labels (monday0 epoch). */
  epoch: string;
};

/** Chart-ready demand profile summary (not the full FreshNet JSON blob). */
export type DemandSummary = {
  scale_mu: number;
  /** Length-7 monday0 means (scale × DOW factors). */
  dow_means: number[];
};

/** Chart-ready arrival law from Snapshot (T-150 AC3.3). */
export type ArrivalSummary = {
  arrival_product: string;
  rung: string;
  mean_f: number;
  sd_f: number;
  f_zero: number;
  curve: { f: number; density: number; cdf?: number }[];
  baseline_curve?: { f: number; density: number }[] | null;
};

/** Per-day belief on the wire after obs catch-up replay. */
export type BeliefHistoryWire = {
  day: number;
  belief: FlatBelief;
};

/** Cold payload from init / reset. */
export type Snapshot = {
  seq: number;
  episode_day: number;
  belief: FlatBelief;
  /** Per-day beliefs after obs-channel catch-up replay (set_obs_channels). */
  belief_history?: BeliefHistoryWire[];
  history?: Day[];
  /** Live lots; each lot may carry `f_values` for within-lot freshness spread. */
  live_lots?: Lot[];
  live_units?: Unit[];
  pipeline?: PipelineOrder[];
  applied_config?: Partial<SimConfig> & Record<string, unknown>;
  schedule?: ScheduleWire;
  demand_summary?: DemandSummary;
  arrival_summary?: ArrivalSummary;
};

/** Hot payload from step / step_n / act. */
export type DayDelta = {
  seq: number;
  episode_day: number;
  day: Day | (Partial<Day> & { day: number } & Record<string, unknown>);
  drop_oldest: boolean;
  belief?: FlatBelief | null;
  live_lots?: Lot[];
  live_units?: Unit[];
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

/** Policy aliases locked in ADR 0117. */
export type ActPolicyName =
  | "damped_sw"
  | "sw"
  | "rollout"
  | "ctl"
  | "rollout_order"
  | "constant"
  | "const"
  | "fixed";

/** Budget / knob fields passed through act (ADR 0117). */
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

/** T-127 tradeoff forecast RPC result. */
export type QForecastEntry = {
  q: number;
  waste_mean: number;
  waste_p10: number;
  waste_p50: number;
  waste_p90: number;
  missed_mean: number;
  missed_p10: number;
  missed_p50: number;
  missed_p90: number;
  joint_hist: {
    waste_bins: number[];
    missed_bins: number[];
    counts: number[][];
  };
};

export type TradeoffForecastWire = {
  candidates: QForecastEntry[];
};

export type TradeoffForecastResult = TradeoffForecastWire;

export type TempTraceByLotWire = {
  lot_id: number;
  times_d: number[];
  temps_c: number[];
};

export type EventDayWire = {
  day: number;
  arrivals: number;
  sales_total: number | null;
  waste_total: number | null;
  sales_by: number[] | null;
  waste_by: number[] | null;
  arrivals_by: number[] | null;
  lot_ids: number[] | null;
  arrival_lot_ids: number[] | null;
  pack_date_days: number | null;
  temp_times_d: number[] | null;
  temp_temps_c: number[] | null;
  temp_traces_by_lot: TempTraceByLotWire[] | null;
};

export type EventsResult = {
  since_day: number;
  days: EventDayWire[];
};

export type EventsWire = EventsResult;

export type { Economics };

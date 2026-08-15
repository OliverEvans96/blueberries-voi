/** Shared domain types for the mock grocery-inventory simulator. */

import type { DemandSummary, FlatBelief, ScheduleWire } from "./engine/types";

export type BeliefHistoryDay = {
  day: number;
  flatBelief: FlatBelief;
};

export type Lot = {
  lot_id: number;
  n: number;
  tau: number;
};

export type Day = {
  day: number;
  lots: Lot[];
  sales_total: number;
  waste_total: number;
  demand: number;
  order_qty: number;
  arrivals: number;
  stockout: number;
  /** Effective age at receipt for today's delivery (null if none). */
  age_at_receipt: number | null;
};

export type Economics = {
  p_sell: number;
  c_unit: number;
  c_waste: number;
  c_stockout: number;
};

/** Filter observation ladder (≡ Python ``filter.types.ScenarioId``). */
export type ScenarioId = "P0" | "P1" | "F1" | "F1s" | "F2a" | "F2";

/**
 * MOD-21 Abdella sampling frame (mock): all six vs corridor subsets.
 * Matches ADR alternatives A / B / C.
 */
export type ArrivalProduct = "abdella_all" | "long_haul" | "short_haul";

export type SimConfig = {
  beta: number;
  eta_ref: number;
  q10: number;
  t_ref_c: number;
  t_store_c: number;
  sigma: number;
  demand_mu: number;
  demand_vm: number;
  case_size: number;
  lead_time: number;
  base_stock: number;
  starting_inv: number;
  seed: number;
  obs_scenario: ScenarioId;
  window_days: number;
  /** MOD-21: which Abdella corridor mix seeds the arrival prior. */
  arrival_product: ArrivalProduct;
  /**
   * FIL-11 / sim.generate_arrival_age: shrink ages toward mix mean
   * (&lt;1 tighter, identification stress).
   */
  spread_scale: number;
  /**
   * MOD-18 teaching knob: °C bias on transit path vs published traces
   * (Arrhenius shift of effective arrival age).
   */
  transit_temp_bias_c: number;
  /** F2a transit-uncertainty SD (arrival_priors.F2A_TRANSIT_UNCERTAINTY_SD). */
  f2a_transit_sd: number;
  /**
   * Reserved STREAM_ARRIVAL_SENSOR: Gaussian noise on lot age at receipt
   * (0 = unused, matching current Python sim).
   */
  sensor_sigma: number;
};

export type DayPnL = {
  day: number;
  revenue: number;
  cost_purchase: number;
  cost_waste: number;
  cost_stockout: number;
  cost_total: number;
  profit: number;
};

export type BeliefGrid = {
  tau_edges: number[];
  count_edges: number[];
  /** Age bins × count bins (K × C) after lot-mass rebin (ADR 0109). */
  density: number[][];
  /** Merged age mass length K; optional presentation field. */
  age_marginal?: number[];
};

export type PipelineOrder = {
  qty: number;
  arrive_on: number;
  days_until: number;
};

export type GhostSeriesPoint = {
  /** Index within the rolling window (0 = oldest in ghost snapshot). */
  i: number;
  waste: number;
  stockout: number;
  sales: number;
  demand: number;
  profit: number;
  profit_cum: number;
};

export type EpisodeGhost = {
  series: GhostSeriesPoint[];
  waste_total: number;
  stockout_total: number;
  profit_cum: number;
  days: number;
};

export type GhostDeltas = {
  waste_rate: number;
  stockouts: number;
  profit_cum: number;
};

export type ViewModel = {
  episode_day: number;
  window_days: number;
  history: Day[];
  economics: Economics;
  config: SimConfig;
  config_dirty: boolean;
  pnl_series: DayPnL[];
  pnl_totals: {
    revenue: number;
    cost: number;
    profit: number;
    today_revenue: number;
    today_cost: number;
    today_profit: number;
  };
  belief: BeliefGrid;
  /** Live truth lots (latest day). */
  live_lots: Lot[];
  /** Rolling FlatBelief per history day (same window as `history`). */
  belief_history: BeliefHistoryDay[];
  on_hand: number;
  effective_inv: number;
  pipeline: PipelineOrder[];
  ghost: EpisodeGhost | null;
  ghost_deltas: GhostDeltas | null;
  case_size: number;
  pending_order: number;
  /** Chart-ready DOW demand profile from Snapshot (T-085 / T-087). */
  demand_summary: DemandSummary | null;
  /** Order calendar wire for protection chrome (T-085 / T-087). */
  schedule: ScheduleWire | null;
};

export type StepInput = {
  order_qty: number;
};

export type HoverDay = number | null;

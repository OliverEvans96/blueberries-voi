/** Shared domain types for the mock grocery-inventory simulator. */

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
};

export type Economics = {
  p_sell: number;
  c_unit: number;
  c_waste: number;
  c_stockout: number;
};

/** Fake physics / logistics knobs (aligned with ModelParams defaults). */
export type ObsScenario = "P0" | "P1" | "P2";

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
  obs_scenario: ObsScenario;
  window_days: number;
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
  density: number[][];
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
  case_size: number;
  pending_order: number;
};

export type StepInput = {
  order_qty: number;
};

export type HoverDay = number | null;

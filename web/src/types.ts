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

export type ChartContext = {
  hoveredDay: HoverDay;
  onHoverDay: (day: HoverDay) => void;
};

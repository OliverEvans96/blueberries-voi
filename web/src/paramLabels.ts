export type ControlTier = "Live" | "Preview" | "Reset" | "Autopilot";

export type ParamLabel = {
  label: string;
  tooltip: string;
  tier: ControlTier;
};

export const PARAM_LABELS: Record<string, ParamLabel> = {
  p_sell: {
    label: "Sell price",
    tooltip: "Revenue per unit sold — updates P&L immediately.",
    tier: "Live",
  },
  c_unit: {
    label: "Unit cost",
    tooltip: "Purchase cost per unit — updates P&L immediately.",
    tier: "Live",
  },
  c_waste: {
    label: "Waste cost",
    tooltip: "Penalty per spoiled unit — updates P&L immediately.",
    tier: "Live",
  },
  c_stockout: {
    label: "Stockout cost",
    tooltip: "Penalty per missed sale — updates P&L immediately.",
    tier: "Live",
  },
  eta_ref: {
    label: "Reference shelf life (η)",
    tooltip: "Baseline days to spoil at reference temperature.",
    tier: "Reset",
  },
  q10: {
    label: "Q10 temperature factor",
    tooltip: "How fast quality drops per 10°C.",
    tier: "Reset",
  },
  t_ref_c: {
    label: "Reference temperature",
    tooltip: "Baseline cold-chain temperature (°C).",
    tier: "Reset",
  },
  t_store_c: {
    label: "Store temperature",
    tooltip: "Cooler temperature at the store (°C).",
    tier: "Reset",
  },
  sigma: {
    label: "Picking selectivity (1/σ)",
    tooltip:
      "Left = uniform picking across lots; right = highly selective (favors fresher lots).",
    tier: "Reset",
  },
  demand_mu: {
    label: "Mean daily demand (μ)",
    tooltip: "Average units demanded per day — preview updates the DOW chart.",
    tier: "Preview",
  },
  demand_vm: {
    label: "Demand variance/mean (V/M)",
    tooltip: "Over-dispersion of daily demand — applies on Reset.",
    tier: "Reset",
  },
  case_size: {
    label: "Case pack size",
    tooltip: "Order quantity snaps to case multiples.",
    tier: "Reset",
  },
  base_stock: {
    label: "Base-stock target",
    tooltip: "Target on-hand for replenishment policy.",
    tier: "Reset",
  },
  lead_time: {
    label: "Lead time (days)",
    tooltip: "Days from order to delivery — flows to session schedule.",
    tier: "Reset",
  },
  delivery_weekdays: {
    label: "Delivery days",
    tooltip:
      "Click weekdays when deliveries arrive; order markers shift with lead time. Applies on Reset.",
    tier: "Reset",
  },
  spread_scale: {
    label: "Arrival spread (FIL-11)",
    tooltip: "Tightens or widens arrival freshness mix.",
    tier: "Reset",
  },
  transit_temp_bias_c: {
    label: "Transit temperature bias",
    tooltip: "°C offset on transit path vs published traces.",
    tier: "Reset",
  },
  seed: {
    label: "Random seed",
    tooltip: "Reshapes the episode on Reset.",
    tier: "Reset",
  },
};

export function paramLabel(id: string): ParamLabel | undefined {
  return PARAM_LABELS[id];
}

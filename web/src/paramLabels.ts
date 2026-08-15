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
  beta: {
    label: "Weibull shape (β)",
    tooltip: "Spoilage curve shape — applies on Reset.",
    tier: "Reset",
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
    label: "Picking variability (σ)",
    tooltip: "Lot-to-lot spread in effective age.",
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
  starting_inv: {
    label: "Starting inventory",
    tooltip: "Units on hand at episode start.",
    tier: "Reset",
  },
  spread_scale: {
    label: "Arrival spread (FIL-11)",
    tooltip: "Tightens or widens arrival-age mix.",
    tier: "Reset",
  },
  transit_temp_bias_c: {
    label: "Transit temperature bias",
    tooltip: "°C offset on transit path vs published traces.",
    tier: "Reset",
  },
  f2a_transit_sd: {
    label: "F2a transit uncertainty",
    tooltip: "Prior width from pack-date ASN — active on F2a rung.",
    tier: "Reset",
  },
  sensor_sigma: {
    label: "Receipt age sensor noise",
    tooltip: "Gaussian noise on measured age at receipt (F2).",
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

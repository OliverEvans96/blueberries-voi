export type ControlTier = "Live" | "Preview" | "Reset" | "Autopilot";

export type ParamLabel = {
  label: string;
  tooltip: string;
  tier: ControlTier;
};

export const PARAM_LABELS: Record<string, ParamLabel> = {
  p_sell: {
    label: "Sell price",
    tooltip:
      "Price customers pay per unit sold, credited to revenue the moment it sells.",
    tier: "Live",
  },
  c_unit: {
    label: "Unit cost",
    tooltip:
      "Purchase cost per delivered unit, deducted from profit as cost of goods.",
    tier: "Live",
  },
  c_waste: {
    label: "Waste cost",
    tooltip:
      "Cost charged per unit that spoils and gets thrown out, on top of its purchase cost.",
    tier: "Live",
  },
  c_stockout: {
    label: "Stockout cost",
    tooltip:
      "Penalty per unit of demand the shelf couldn't meet, on top of the lost margin.",
    tier: "Live",
  },
  eta_ref: {
    label: "Reference shelf life (η)",
    tooltip:
      "Shelf life in days at the reference temperature (default: 14 days at 0°C). Drives both in-store aging and transit arrival freshness. Higher values mean fruit spoils more slowly on average.",
    tier: "Reset",
  },
  q10: {
    label: "Q10 temperature factor",
    tooltip:
      "How much faster freshness decays per 10°C above the reference temperature (default: 3×). Affects both in-store aging and transit.",
    tier: "Reset",
  },
  t_ref_c: {
    label: "Reference temperature",
    tooltip:
      "The temperature reference shelf life and Q10 are measured against (default: 0°C). Not a real storage condition — just the anchor other temperatures are compared to.",
    tier: "Reset",
  },
  t_store_c: {
    label: "Store temperature",
    tooltip:
      "Constant temperature assumed for the retail cooler. Higher values speed up in-store spoilage via the Q10 factor.",
    tier: "Reset",
  },
  sigma: {
    label: "Picking selectivity (1/σ)",
    tooltip:
      "How strongly sales favor fresher units: left is random picking, right is a strongly fresh-biased lottery. Never strict oldest-first — every unspoiled unit always has some chance of being picked.",
    tier: "Reset",
  },
  demand_mu: {
    label: "Mean daily demand (μ)",
    tooltip:
      "Average units demanded on a typical day, scaled up or down by the day-of-week and weekly calendar pattern.",
    tier: "Preview",
  },
  demand_vm: {
    label: "Demand variance/mean (V/M)",
    tooltip:
      "How much more scattered daily demand is than a simple random count with the same mean (default: 2.0, matching real retail demand). Applies on Reset.",
    tier: "Reset",
  },
  case_size: {
    label: "Case pack size",
    tooltip:
      "Units packed per case. Orders are rounded to the nearest whole case before being sent.",
    tier: "Reset",
  },
  lead_time: {
    label: "Lead time (days)",
    tooltip:
      "Days between placing an order and its arrival. A longer lead time means the policy must plan further ahead.",
    tier: "Reset",
  },
  delivery_weekdays: {
    label: "Delivery days",
    tooltip:
      "Weekdays deliveries can arrive on; order days are set automatically (delivery day minus lead time). Orders on other days are dropped, not queued. Takes effect on Reset.",
    tier: "Reset",
  },
  spread_scale: {
    label: "Arrival spread (FIL-11)",
    tooltip:
      "How spread out delivered units' freshness is around the lot's average. 1.0 is the natural mix; below tightens it, above widens it.",
    tier: "Reset",
  },
  arrival_product: {
    label: "Arrival corridor",
    tooltip:
      "Abdella corridor mixture (abdella_mix): each delivery draws short_haul (80%) or long_haul (20%) for trip duration and temperature; illustrative leaf lanes are not exposed as separate studio chips.",
    tier: "Reset",
  },
  transit_temp_bias_c: {
    label: "Transit temperature bias",
    tooltip:
      "Offset added to the simulated transit temperature, to explore a colder- or warmer-running route. Shifts delivered freshness, though the arrival-freshness chart doesn't yet reflect it (known display gap).",
    tier: "Reset",
  },
  seed: {
    label: "Random seed",
    tooltip:
      "Seed for every random draw in the episode (demand, transit, freshness decay). Change it and Reset to try a different but equally valid run.",
    tier: "Reset",
  },
};

export function paramLabel(id: string): ParamLabel | undefined {
  return PARAM_LABELS[id];
}

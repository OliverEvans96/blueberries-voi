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
      "The price customers pay per unit sold, credited to the day's revenue the moment a sale happens. It's a live parameter, so moving the slider immediately rescales the profit-and-loss chart without needing a Reset.",
    tier: "Live",
  },
  c_unit: {
    label: "Unit cost",
    tooltip:
      "The purchase cost charged for each unit that arrives in a delivery, deducted from the day's profit as cost of goods. It's live, so it immediately rescales the P&L chart without needing a Reset.",
    tier: "Live",
  },
  c_waste: {
    label: "Waste cost",
    tooltip:
      "The cost charged per unit that spoils on the shelf and gets thrown out, on top of the purchase cost already sunk into it. It's live, so raising it immediately makes over-ordering show up as a bigger loss in the P&L chart.",
    tier: "Live",
  },
  c_stockout: {
    label: "Stockout cost",
    tooltip:
      "The penalty charged per unit of demand that goes unmet once the shelf empties, on top of the margin already lost on that missed sale. It's live, so raising it immediately makes under-ordering show up as a bigger loss in the P&L chart.",
    tier: "Live",
  },
  eta_ref: {
    label: "Reference shelf life (η)",
    tooltip:
      "The shelf life, in reference-days, a unit gets at the reference temperature — the model default is 14 days at 0°C. It sets the average daily freshness loss the gamma-aging process draws from, so raising it means fruit spoils more slowly on average.",
    tier: "Reset",
  },
  q10: {
    label: "Q10 temperature factor",
    tooltip:
      "How much faster freshness decays for every 10°C above the reference temperature; the default multiplier is 3.0, meaning aging roughly triples per 10°C of warming. The same factor accelerates both in-store aging and freshness loss during transit.",
    tier: "Reset",
  },
  t_ref_c: {
    label: "Reference temperature",
    tooltip:
      "The zero point of the temperature scale that reference shelf life and the Q10 factor are measured against — the model default is 0°C. It isn't a real storage condition on its own; it's the anchor other temperatures are compared to when computing how much faster or slower fruit ages.",
    tier: "Reset",
  },
  t_store_c: {
    label: "Store temperature",
    tooltip:
      "The constant temperature assumed for the retail cooler where units sit until sold. Raising it accelerates the in-store gamma-aging process through the Q10 factor, so shelf fruit loses freshness faster and spoils sooner.",
    tier: "Reset",
  },
  sigma: {
    label: "Picking selectivity (1/σ)",
    tooltip:
      "Controls how strongly a sale favors the freshest units on the shelf: slide left toward uniform, random picking, and right toward a strongly fresh-biased lottery where fresher punnets are far more likely to be picked. Even at the most selective end, every unspoiled unit still has some chance of being picked, and units are never pulled in strict oldest-first order.",
    tier: "Reset",
  },
  demand_mu: {
    label: "Mean daily demand (μ)",
    tooltip:
      "Sets the average number of units demanded on a typical day, which the calendar's day-of-week and week-to-week multipliers then scale up or down for any particular day. Dragging it previews the reshaped day-of-week demand chart immediately.",
    tier: "Preview",
  },
  demand_vm: {
    label: "Demand variance/mean (V/M)",
    tooltip:
      "How much more scattered daily demand is than a simple random count with the same mean; the default of 2.0 makes the day's demand variance twice its mean instead of equal to it, matching real retail demand's tendency to overdisperse. The new value applies on Reset, so already-simulated days aren't rewritten retroactively.",
    tier: "Reset",
  },
  case_size: {
    label: "Case pack size",
    tooltip:
      "The number of units packed per case. The replenishment policy's order-up-to gap is rounded to the nearest whole case (not always up) before it's sent, so delivered quantities always land in multiples of this number.",
    tier: "Reset",
  },
  base_stock: {
    label: "Base-stock target",
    tooltip:
      "A reference on-hand target shown on the effective-inventory chart. It isn't currently consumed by the live controller's ordering math — damped_sw and rollout both compute their own order-up-to target from the demand quantile and effective inventory each day — so this slider only moves the chart's reference line, since a real base-stock ordering policy hasn't shipped on the backend yet.",
    tier: "Reset",
  },
  lead_time: {
    label: "Lead time (days)",
    tooltip:
      "The number of days between placing an order and its units arriving. It shifts where order and delivery markers land on the session's timeline, and a longer lead time forces the policy to protect against demand over a longer, riskier window before the next delivery.",
    tier: "Reset",
  },
  delivery_weekdays: {
    label: "Delivery days",
    tooltip:
      "The weekdays a delivery truck is allowed to arrive on; order weekdays are derived automatically from these minus the lead time. An order submitted on any other day isn't placed at all — it's dropped rather than queued for the next eligible day — and toggling these reshapes the whole session's order-and-delivery schedule, so the change only takes effect after a Reset re-simulates the run.",
    tier: "Reset",
  },
  spread_scale: {
    label: "Arrival spread (FIL-11)",
    tooltip:
      "Scales how much delivered units' freshness values are spread around the lot's mean, without changing the mean itself. A value of 1.0 leaves the natural arrival mix unchanged; below 1.0 tightens it so a lot's units look more uniform, above 1.0 widens it so some units arrive noticeably fresher or more degraded than others.",
    tier: "Reset",
  },
  transit_temp_bias_c: {
    label: "Transit temperature bias",
    tooltip:
      "An offset, in degrees C, added to the simulated transit temperature for the current run, letting you explore a colder- or warmer-running corridor. It does shift the freshness of units actually delivered, but a known display gap means the arrival-freshness chart shown in the studio doesn't update to reflect it.",
    tier: "Reset",
  },
  seed: {
    label: "Random seed",
    tooltip:
      "The seed driving every random draw in the episode — demand, transit duration and temperature, within-pallet position, and daily freshness decrements. Changing it and pressing Reset produces a different but equally valid episode, useful for checking whether a result holds up across randomness rather than a lucky run.",
    tier: "Reset",
  },
};

export function paramLabel(id: string): ParamLabel | undefined {
  return PARAM_LABELS[id];
}

/**
 * Scenario-aware plot/control gating (T-124 / ADR 0086 / T-119 audit).
 */
import { STUDIO_SECTIONS } from "./sections";
import type { ScenarioId } from "./types";

export type Availability = "show" | "dim" | "unavailable";

/** Canonical studio plot slot ids (store + run + focus + arrival rug). */
function collectPlotIds(): string[] {
  const fromSections = STUDIO_SECTIONS.flatMap((s) => s.plotIds);
  const store = ["store-sales", "store-stockout", "store-lots", "store-spoilage"];
  const run = ["run-pnl-totals", "run-pnl-spark"];
  const extra = ["plot-arrival-prior-rug"];
  return [...new Set([...store, ...run, ...fromSections, ...extra])].sort();
}

/** Slider ids from controls.ts CONFIG_SLIDERS + PRICE_SLIDERS. */
export const ALL_CONTROL_IDS: string[] = [
  "base_stock",
  "c_stockout",
  "c_unit",
  "c_waste",
  "case_size",
  "demand_mu",
  "demand_vm",
  "eta_ref",
  "f2a_transit_sd",
  "p_sell",
  "q10",
  "seed",
  "sensor_sigma",
  "sigma",
  "spread_scale",
  "starting_inv",
  "t_ref_c",
  "t_store_c",
  "transit_temp_bias_c",
].sort();

export const ALL_PLOT_IDS: string[] = collectPlotIds();

const PLOT_RULES: Partial<Record<string, Partial<Record<ScenarioId, Availability>>>> = {
  "store-spoilage": {
    P0: "unavailable",
  },
  "plot-arrival-prior-rug": {
    P0: "unavailable",
    P1: "unavailable",
    F1: "unavailable",
    F1s: "unavailable",
    F2a: "unavailable",
    F2: "show",
  },
};

const CONTROL_RULES: Partial<Record<string, Partial<Record<ScenarioId, Availability>>>> = {
  f2a_transit_sd: {
    P0: "dim",
    P1: "dim",
    F1: "dim",
    F1s: "dim",
    F2a: "show",
    F2: "dim",
  },
  sensor_sigma: {
    P0: "dim",
    P1: "dim",
    F1: "dim",
    F1s: "dim",
    F2a: "dim",
    F2: "show",
  },
};

function lookup(
  rules: Partial<Record<string, Partial<Record<ScenarioId, Availability>>>>,
  id: string,
  scenario: ScenarioId,
): Availability {
  return rules[id]?.[scenario] ?? "show";
}

export function plotAvailability(plotId: string, scenario: ScenarioId): Availability {
  return lookup(PLOT_RULES, plotId, scenario);
}

export function controlAvailability(
  controlId: string,
  scenario: ScenarioId,
): Availability {
  return lookup(CONTROL_RULES, controlId, scenario);
}

/** Whether arrival prior receipt rug may render (F2 or showTruth). */
export function arrivalRugAvailable(
  scenario: ScenarioId,
  showTruth: boolean,
): boolean {
  if (showTruth) return true;
  return plotAvailability("plot-arrival-prior-rug", scenario) === "show";
}

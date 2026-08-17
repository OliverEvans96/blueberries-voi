/**
 * Scenario-aware plot/control gating (T-124 / T-128 ObsChannels).
 */
import { STUDIO_SECTIONS } from "./sections";
import type { ObsChannels, ScenarioId } from "./types";

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
  "lead_time",
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

function spoilageAvailable(ch: ObsChannels): Availability {
  return ch.waste === "none" ? "unavailable" : "show";
}

function packDateControlsAvailable(ch: ObsChannels): Availability {
  return ch.deliveries === "pack_date_per_lot" ? "show" : "dim";
}

export function channelAvailability(
  id: string,
  channels: ObsChannels,
): Availability {
  if (id === "store-spoilage") return spoilageAvailable(channels);
  if (id === "plot-arrival-prior-rug") {
    return ch.deliveries === "pack_date_per_lot" ? "show" : "unavailable";
  }
  if (id === "f2a_transit_sd" || id === "sensor_sigma") {
    return packDateControlsAvailable(channels);
  }
  return "show";
}

export function plotAvailability(
  plotId: string,
  scenarioOrChannels: ScenarioId | ObsChannels,
): Availability {
  if (typeof scenarioOrChannels === "string") {
    return channelAvailability(plotId, channelsFromLegacyScenario(scenarioOrChannels));
  }
  return channelAvailability(plotId, scenarioOrChannels);
}

export function controlAvailability(
  controlId: string,
  scenarioOrChannels: ScenarioId | ObsChannels,
): Availability {
  if (typeof scenarioOrChannels === "string") {
    return channelAvailability(controlId, channelsFromLegacyScenario(scenarioOrChannels));
  }
  return channelAvailability(controlId, scenarioOrChannels);
}

function channelsFromLegacyScenario(scenario: ScenarioId): ObsChannels {
  const map: Record<ScenarioId, ObsChannels> = {
    P0: { pos: "upc_only", waste: "none", deliveries: "quantity_only" },
    P1: { pos: "upc_only", waste: "daily_counts", deliveries: "quantity_only" },
    F1: { pos: "lot_id", waste: "daily_counts", deliveries: "quantity_only" },
    F1s: { pos: "upc_only", waste: "lot_id", deliveries: "quantity_only" },
    F2a: {
      pos: "upc_only",
      waste: "daily_counts",
      deliveries: "pack_date_per_lot",
    },
    F2: { pos: "lot_id", waste: "lot_id", deliveries: "pack_date_per_lot" },
  };
  return map[scenario];
}

/** Whether arrival prior receipt rug may render (pack_date channel or showTruth). */
export function arrivalRugAvailable(
  channels: ObsChannels,
  showTruth: boolean,
): boolean {
  if (showTruth) return true;
  return channelAvailability("plot-arrival-prior-rug", channels) === "show";
}

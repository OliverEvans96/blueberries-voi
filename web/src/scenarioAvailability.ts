/**
 * Scenario-aware plot/control gating (T-124 / T-128 ObsChannels).
 */
import { STUDIO_SECTIONS } from "./sections";
import type { ObsChannels, ScenarioId } from "./types";
import { channelsForPreset } from "./obsMask";

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
  "t_ref_c",
  "t_store_c",
  "transit_temp_bias_c",
].sort();

export const ALL_PLOT_IDS: string[] = collectPlotIds();

function spoilageAvailable(ch: ObsChannels): Availability {
  return ch.scan_waste ? "show" : "unavailable";
}

function packDateControlsAvailable(ch: ObsChannels): Availability {
  return ch.delivery_history === "pack_date" ? "show" : "dim";
}

export function channelAvailability(
  id: string,
  channels: ObsChannels,
): Availability {
  if (id === "store-spoilage") return spoilageAvailable(channels);
  if (id === "plot-arrival-prior-rug") {
    return channels.delivery_history === "pack_date" ? "show" : "unavailable";
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
  return channelsForPreset(scenario);
}

/** Whether arrival prior receipt rug may render (pack_date channel or showTruth). */
export function arrivalRugAvailable(
  channels: ObsChannels,
  showTruth: boolean,
): boolean {
  if (showTruth) return true;
  return channelAvailability("plot-arrival-prior-rug", channels) === "show";
}

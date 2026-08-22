import type { ComponentType } from "react";
import type { ObsChannels, ObsScenarioKey } from "../types";
import { plotAvailability } from "../scenarioAvailability";
import { ChartUnavailable } from "./ChartUnavailable";

export type StoreSpoilageSlot =
  | { kind: "unavailable"; component: typeof ChartUnavailable }
  | { kind: "series" };

export function resolveStoreSpoilageSlot(opts: {
  scenario?: ObsScenarioKey;
  channels?: ObsChannels;
  showTruth: boolean;
}): StoreSpoilageSlot {
  void opts.showTruth;
  const scenarioPreset =
    opts.scenario && opts.scenario !== "custom" ? opts.scenario : "P1";
  const avail = opts.channels
    ? plotAvailability("store-spoilage", opts.channels)
    : plotAvailability("store-spoilage", scenarioPreset);
  if (avail === "unavailable") {
    return { kind: "unavailable", component: ChartUnavailable };
  }
  return { kind: "series" };
}

export type ChartSlotComponent = ComponentType<{
  plotId: string;
  caption: string;
}>;

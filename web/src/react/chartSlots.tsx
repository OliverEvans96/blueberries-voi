import type { ComponentType } from "react";
import type { ObsChannels, ScenarioId } from "../types";
import { plotAvailability } from "../scenarioAvailability";
import { ChartUnavailable } from "./ChartUnavailable";

export type StoreSpoilageSlot =
  | { kind: "unavailable"; component: typeof ChartUnavailable }
  | { kind: "series" };

export function resolveStoreSpoilageSlot(opts: {
  scenario?: ScenarioId;
  channels?: ObsChannels;
  showTruth: boolean;
}): StoreSpoilageSlot {
  void opts.showTruth;
  const avail = opts.channels
    ? plotAvailability("store-spoilage", opts.channels)
    : plotAvailability("store-spoilage", opts.scenario ?? "P1");
  if (avail === "unavailable") {
    return { kind: "unavailable", component: ChartUnavailable };
  }
  return { kind: "series" };
}

export type ChartSlotComponent = ComponentType<{
  plotId: string;
  caption: string;
}>;

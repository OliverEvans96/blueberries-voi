import type { ComponentType } from "react";
import type { ScenarioId } from "../types";
import { plotAvailability } from "../scenarioAvailability";
import { ChartUnavailable } from "./ChartUnavailable";

export type StoreSpoilageSlot =
  | { kind: "unavailable"; component: typeof ChartUnavailable }
  | { kind: "series" };

export function resolveStoreSpoilageSlot(opts: {
  scenario: ScenarioId;
  showTruth: boolean;
}): StoreSpoilageSlot {
  void opts.showTruth;
  const avail = plotAvailability("store-spoilage", opts.scenario);
  if (avail === "unavailable") {
    return { kind: "unavailable", component: ChartUnavailable };
  }
  return { kind: "series" };
}

export type ChartSlotComponent = ComponentType<{
  plotId: string;
  caption: string;
}>;

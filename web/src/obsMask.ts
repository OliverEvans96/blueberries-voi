/**
 * Observation masks — TypeScript port of crates/voi_core/src/obs.rs (global scan model).
 */
import type { ObsScenarioKey, ScenarioId } from "./types";
export type ObsMask = {
  arrivals: boolean;
  sales_total: boolean;
  waste_total: boolean;
  sales_by_lot: boolean;
  waste_by_lot: boolean;
  pack_date: boolean;
  age_at_receipt: boolean;
  lot_ids_live: boolean;
  arrival_lot_ids: boolean;
  temperature_history: boolean;
};

export type CodeType = "upc" | "gsin";
export type DeliveryHistory = "none" | "pack_date" | "temperature_history";

export type ObsChannels = {
  code_type: CodeType;
  scan_waste: boolean;
  delivery_history: DeliveryHistory;
};

export type RichObsWire = {
  day?: number;
  arrivals: number;
  sales_total?: number | null;
  waste_total?: number | null;
  sales_by?: number[] | null;
  waste_by?: number[] | null;
  lot_ids?: number[] | null;
  arrival_lot_ids?: number[] | null;
  age_at_receipt?: number | null;
  pack_date_days?: number | null;
  temp_times_d?: number[] | null;
  temp_temps_c?: number[] | null;
};

export type MaskedObsWire = RichObsWire;

const DEFAULT_MASK: ObsMask = {
  arrivals: false,
  sales_total: false,
  waste_total: false,
  sales_by_lot: false,
  waste_by_lot: false,
  pack_date: false,
  age_at_receipt: false,
  lot_ids_live: false,
  arrival_lot_ids: false,
  temperature_history: false,
};

export const DEFAULT_OBS_CHANNELS: ObsChannels = {
  code_type: "upc",
  scan_waste: true,
  delivery_history: "none",
};

const PRESET_CHANNELS: Record<string, ObsChannels> = {
  P0: { code_type: "upc", scan_waste: false, delivery_history: "none" },
  P1: DEFAULT_OBS_CHANNELS,
  F1: { code_type: "gsin", scan_waste: true, delivery_history: "none" },
  F1s: { code_type: "gsin", scan_waste: true, delivery_history: "none" },
  F2a: { code_type: "upc", scan_waste: true, delivery_history: "pack_date" },
  F2: { code_type: "gsin", scan_waste: true, delivery_history: "pack_date" },
  F3: {
    code_type: "gsin",
    scan_waste: true,
    delivery_history: "temperature_history",
  },
};

export const OBS_PRESET_IDS: ScenarioId[] = [
  "P0",
  "P1",
  "F1",
  "F1s",
  "F2a",
  "F2",
  "F3",
];

export function channelsEqual(a: ObsChannels, b: ObsChannels): boolean {
  return (
    a.code_type === b.code_type &&
    a.scan_waste === b.scan_waste &&
    a.delivery_history === b.delivery_history
  );
}

/** Map live channels to a ladder id, F1s when explicit, or ``custom``. */
export function resolveDisplayObsScenario(
  channels: ObsChannels,
  explicitPreset?: ScenarioId,
): ObsScenarioKey {
  for (const id of OBS_PRESET_IDS) {
    if (!channelsEqual(channels, channelsForPreset(id))) continue;
    if (explicitPreset === "F1s" && id === "F1") return "F1s";
    return id;
  }
  return "custom";
}

export function channelsForPreset(scenario: string): ObsChannels {
  if (scenario === "B-state") {
    throw new Error(
      "SCN-B-state is a verification bypass, not an ObsMask; do not fabricate observations via channelsForPreset",
    );
  }
  const ch = PRESET_CHANNELS[scenario];
  if (!ch) {
    throw new Error(`Unknown scenario for ObsMask: ${JSON.stringify(scenario)}`);
  }
  return { ...ch };
}

export function channelsCacheKey(ch: ObsChannels): string {
  const waste = ch.scan_waste ? "1" : "0";
  return `code=${ch.code_type}|waste=${waste}|hist=${ch.delivery_history}`;
}

export function maskFromChannels(ch: ObsChannels): ObsMask {
  const m: ObsMask = {
    ...DEFAULT_MASK,
    arrivals: true,
    sales_total: true,
  };
  if (ch.code_type === "gsin") {
    m.sales_by_lot = true;
    m.lot_ids_live = true;
    m.arrival_lot_ids = true;
  }
  if (ch.scan_waste) {
    m.waste_total = true;
    if (ch.code_type === "gsin") {
      m.waste_by_lot = true;
    }
  }
  if (ch.delivery_history === "pack_date") {
    m.pack_date = true;
  } else if (ch.delivery_history === "temperature_history") {
    m.temperature_history = true;
  }
  return m;
}

export function maskFor(scenario: string): ObsMask {
  return maskFromChannels(channelsForPreset(scenario));
}

export function applyMask(rich: RichObsWire, mask: ObsMask): MaskedObsWire {
  return {
    day: rich.day,
    arrivals: rich.arrivals,
    sales_total: mask.sales_total ? (rich.sales_total ?? null) : null,
    waste_total: mask.waste_total ? (rich.waste_total ?? null) : null,
    sales_by: mask.sales_by_lot ? (rich.sales_by ?? null) : null,
    waste_by: mask.waste_by_lot ? (rich.waste_by ?? null) : null,
    lot_ids: mask.lot_ids_live ? (rich.lot_ids ?? null) : null,
    arrival_lot_ids: mask.arrival_lot_ids ? (rich.arrival_lot_ids ?? null) : null,
    pack_date_days: mask.pack_date ? (rich.pack_date_days ?? null) : null,
    age_at_receipt: mask.age_at_receipt ? (rich.age_at_receipt ?? null) : null,
    temp_times_d: mask.temperature_history ? (rich.temp_times_d ?? null) : null,
    temp_temps_c: mask.temperature_history ? (rich.temp_temps_c ?? null) : null,
  };
}

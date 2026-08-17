/**
 * Observation masks — TypeScript port of crates/voi_core/src/obs.rs (T-127 / T-128).
 */
export type ObsMask = {
  arrivals: boolean;
  sales_total: boolean;
  waste_total: boolean;
  sales_by_lot: boolean;
  waste_by_lot: boolean;
  pack_date: boolean;
  age_at_receipt: boolean;
  lot_ids_live: boolean;
};

export type PosChannel = "upc_only" | "lot_id";
export type WasteChannel = "none" | "daily_counts" | "lot_id";
export type DeliveryChannel = "quantity_only" | "pack_date_per_lot";

export type ObsChannels = {
  pos: PosChannel;
  waste: WasteChannel;
  deliveries: DeliveryChannel;
};

export type RichObsWire = {
  day?: number;
  arrivals: number;
  sales_total?: number | null;
  waste_total?: number | null;
  sales_by?: number[] | null;
  waste_by?: number[] | null;
  lot_ids?: number[] | null;
  age_at_receipt?: number | null;
  pack_date_days?: number | null;
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
};

export const DEFAULT_OBS_CHANNELS: ObsChannels = {
  pos: "upc_only",
  waste: "daily_counts",
  deliveries: "quantity_only",
};

const PRESET_CHANNELS: Record<string, ObsChannels> = {
  P0: { pos: "upc_only", waste: "none", deliveries: "quantity_only" },
  P1: DEFAULT_OBS_CHANNELS,
  F1: { pos: "lot_id", waste: "daily_counts", deliveries: "quantity_only" },
  F1s: { pos: "upc_only", waste: "lot_id", deliveries: "quantity_only" },
  F2a: {
    pos: "upc_only",
    waste: "daily_counts",
    deliveries: "pack_date_per_lot",
  },
  F2: {
    pos: "lot_id",
    waste: "lot_id",
    deliveries: "pack_date_per_lot",
  },
};

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
  return `pos=${ch.pos}|waste=${ch.waste}|deliveries=${ch.deliveries}`;
}

export function maskFromChannels(ch: ObsChannels): ObsMask {
  const m: ObsMask = {
    ...DEFAULT_MASK,
    arrivals: true,
    sales_total: true,
  };
  if (ch.pos === "lot_id") {
    m.sales_by_lot = true;
    m.lot_ids_live = true;
  }
  if (ch.waste === "daily_counts") {
    m.waste_total = true;
  } else if (ch.waste === "lot_id") {
    m.waste_total = true;
    m.waste_by_lot = true;
    m.lot_ids_live = true;
  }
  if (ch.deliveries === "pack_date_per_lot") {
    m.pack_date = true;
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
    pack_date_days: mask.pack_date ? (rich.pack_date_days ?? null) : null,
    age_at_receipt: mask.age_at_receipt ? (rich.age_at_receipt ?? null) : null,
  };
}

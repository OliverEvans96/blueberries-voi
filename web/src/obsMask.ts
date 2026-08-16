/**
 * Observation masks — TypeScript port of crates/voi_core/src/obs.rs (T-127).
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

export function maskFor(scenario: string): ObsMask {
  if (scenario === "B-state") {
    throw new Error(
      "SCN-B-state is a verification bypass, not an ObsMask; do not fabricate observations via maskFor",
    );
  }
  switch (scenario) {
    case "P0":
      return { ...DEFAULT_MASK, arrivals: true, sales_total: true };
    case "P1":
      return {
        ...DEFAULT_MASK,
        arrivals: true,
        sales_total: true,
        waste_total: true,
      };
    case "F1":
      return {
        ...DEFAULT_MASK,
        arrivals: true,
        sales_total: true,
        waste_total: true,
        sales_by_lot: true,
        lot_ids_live: true,
      };
    case "F1s":
      return {
        ...DEFAULT_MASK,
        arrivals: true,
        sales_total: true,
        waste_total: true,
        waste_by_lot: true,
        lot_ids_live: true,
      };
    case "F2a":
      return {
        ...DEFAULT_MASK,
        arrivals: true,
        sales_total: true,
        waste_total: true,
        pack_date: true,
      };
    case "F2":
      return {
        ...DEFAULT_MASK,
        arrivals: true,
        sales_total: true,
        waste_total: true,
        sales_by_lot: true,
        waste_by_lot: true,
        age_at_receipt: true,
        lot_ids_live: true,
      };
    default:
      throw new Error(`Unknown scenario for ObsMask: ${JSON.stringify(scenario)}`);
  }
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

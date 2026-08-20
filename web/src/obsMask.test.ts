/**
 * T-127 RED (qa-obs-mask): obsMask.ts port — maskFor / applyMask parity with Rust obs.rs.
 */
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const MODULE = join(HERE, "obsMask.ts");

type ObsMask = {
  arrivals: boolean;
  sales_total: boolean;
  waste_total: boolean;
  sales_by_lot: boolean;
  waste_by_lot: boolean;
  pack_date: boolean;
  age_at_receipt: boolean;
  lot_ids_live: boolean;
};

type RichObsWire = {
  day: number;
  arrivals: number;
  sales_total?: number | null;
  waste_total?: number | null;
  sales_by?: number[] | null;
  waste_by?: number[] | null;
  lot_ids?: number[] | null;
  age_at_receipt?: number | null;
  pack_date_days?: number | null;
};

type ObsMaskModule = {
  maskFor: (scenario: string) => ObsMask;
  applyMask: (rich: RichObsWire, mask: ObsMask) => RichObsWire;
};

async function loadObsMask(): Promise<ObsMaskModule | null> {
  if (!existsSync(MODULE)) return null;
  try {
    return (await import(MODULE)) as ObsMaskModule;
  } catch {
    return null;
  }
}

function presentFields(m: ObsMask): Record<string, boolean> {
  return {
    arrivals: m.arrivals,
    sales_total: m.sales_total,
    waste_total: m.waste_total,
    sales_by_lot: m.sales_by_lot,
    waste_by_lot: m.waste_by_lot,
    pack_date: m.pack_date,
    age_at_receipt: m.age_at_receipt,
    lot_ids_live: m.lot_ids_live,
  };
}

const RICH: RichObsWire = {
  day: 2,
  arrivals: 8,
  sales_total: 4,
  waste_total: 2,
  sales_by: [3, 1],
  waste_by: [2, 0],
  lot_ids: [10, 11],
  age_at_receipt: 2.0,
  pack_date_days: 3,
};

describe("obsMask (T-127 AC-obs-mask)", () => {
  it("ships obsMask.ts with maskFor and applyMask", async () => {
    const mod = await loadObsMask();
    expect(mod, "expected web/src/obsMask.ts").not.toBeNull();
    expect(typeof mod!.maskFor).toBe("function");
    expect(typeof mod!.applyMask).toBe("function");
  });

  it("mask_for P0: arrivals + sales_total only", async () => {
    const mod = await loadObsMask();
    const f = presentFields(mod!.maskFor("P0"));
    expect(f.arrivals).toBe(true);
    expect(f.sales_total).toBe(true);
    expect(f.waste_total).toBe(false);
    expect(f.sales_by_lot).toBe(false);
    expect(f.waste_by_lot).toBe(false);
    expect(f.pack_date).toBe(false);
    expect(f.age_at_receipt).toBe(false);
    expect(f.lot_ids_live).toBe(false);
  });

  it("mask_for P1 adds waste_total", async () => {
    const mod = await loadObsMask();
    const m = mod!.maskFor("P1");
    expect(m.arrivals && m.sales_total && m.waste_total).toBe(true);
    expect(m.sales_by_lot || m.waste_by_lot || m.lot_ids_live).toBe(false);
  });

  it("mask_for F1 adds sales_by_lot, lot_ids_live, and waste_by_lot", async () => {
    const mod = await loadObsMask();
    const m = mod!.maskFor("F1");
    expect(m.waste_total && m.sales_by_lot && m.lot_ids_live && m.waste_by_lot).toBe(true);
    expect(m.pack_date || m.age_at_receipt).toBe(false);
  });

  it("mask_for F1s matches F1 under scan model", async () => {
    const mod = await loadObsMask();
    expect(mod!.maskFor("F1s")).toEqual(mod!.maskFor("F1"));
  });

  it("mask_for F2a is P1 plus pack_date", async () => {
    const mod = await loadObsMask();
    const m = mod!.maskFor("F2a");
    expect(m.waste_total && m.pack_date).toBe(true);
    expect(m.sales_by_lot || m.waste_by_lot || m.lot_ids_live).toBe(false);
  });

  it("mask_for F2 has maps and pack_date — not age_at_receipt", async () => {
    const mod = await loadObsMask();
    const m = mod!.maskFor("F2");
    expect(m.waste_total && m.sales_by_lot && m.waste_by_lot).toBe(true);
    expect(m.lot_ids_live && m.pack_date && m.arrival_lot_ids).toBe(true);
    expect(m.age_at_receipt).toBe(false);
  });

  it("mask_for P2 and B-state throw like Rust", async () => {
    const mod = await loadObsMask();
    expect(() => mod!.maskFor("P2")).toThrow(/unknown|P2/i);
    expect(() => mod!.maskFor("B-state")).toThrow(/bypass|B-state|fabricate/i);
  });

  it("applyMask P0 omits waste — never invents zero", async () => {
    const mod = await loadObsMask();
    const obs = mod!.applyMask(RICH, mod!.maskFor("P0"));
    expect(obs.arrivals).toBe(8);
    expect(obs.sales_total).toBe(4);
    expect(obs.waste_total).toBeNull();
    expect(obs.sales_by).toBeNull();
    expect(obs.waste_by).toBeNull();
    expect(obs.lot_ids).toBeNull();
    expect(obs.pack_date_days).toBeNull();
    expect(obs.age_at_receipt).toBeNull();
  });

  it("applyMask F2 keeps maps and pack_date, strips age_at_receipt", async () => {
    const mod = await loadObsMask();
    const obs = mod!.applyMask(RICH, mod!.maskFor("F2"));
    expect(obs.waste_total).toBe(2);
    expect(obs.sales_by).toEqual([3, 1]);
    expect(obs.waste_by).toEqual([2, 0]);
    expect(obs.lot_ids).toEqual([10, 11]);
    expect(obs.pack_date_days).toBe(3);
    expect(obs.age_at_receipt).toBeNull();
  });
});

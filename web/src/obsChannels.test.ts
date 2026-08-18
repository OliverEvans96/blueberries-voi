/**
 * T-128 RED: ObsChannels maskFromChannels parity + DecisionRail toggles.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC = dirname(fileURLToPath(import.meta.url));

function readSrc(rel: string): string {
  return readFileSync(join(SRC, rel), "utf8");
}

type ObsChannels = {
  pos: "upc_only" | "lot_id";
  waste: "none" | "daily_counts" | "lot_id";
  deliveries: "quantity_only" | "pack_date_per_lot";
};

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

async function loadObsMask() {
  return (await import("./obsMask")) as {
    maskFromChannels: (ch: ObsChannels) => ObsMask;
    channelsForPreset: (id: string) => ObsChannels;
    channelsCacheKey: (ch: ObsChannels) => string;
  };
}

const ALL_CHANNELS: ObsChannels[] = (["upc_only", "lot_id"] as const).flatMap((pos) =>
  (["none", "daily_counts", "lot_id"] as const).flatMap((waste) =>
    (["quantity_only", "pack_date_per_lot"] as const).map((deliveries) => ({
      pos,
      waste,
      deliveries,
    })),
  ),
);

describe("T-128 maskFromChannels", () => {
  it("covers all twelve orthogonal combos", async () => {
    const { maskFromChannels } = await loadObsMask();
    for (const ch of ALL_CHANNELS) {
      const m = maskFromChannels(ch);
      expect(m.arrivals && m.sales_total).toBe(true);
      expect(m.age_at_receipt).toBe(false);
      if (ch.deliveries === "pack_date_per_lot") expect(m.pack_date).toBe(true);
      if (ch.waste === "none") expect(m.waste_total).toBe(false);
    }
  });

  it("F2 preset compiles to pack_date channels", async () => {
    const { channelsForPreset, maskFromChannels } = await loadObsMask();
    const ch = channelsForPreset("F2");
    expect(ch.deliveries).toBe("pack_date_per_lot");
    const m = maskFromChannels(ch);
    expect(m.pack_date).toBe(true);
    expect(m.age_at_receipt).toBe(false);
  });
});

describe("T-128 SecondaryChrome toggles", () => {
  it("SecondaryChrome.tsx uses obs channel toggles not ladder chips", () => {
    const src = readSrc("react/SecondaryChrome.tsx");
    expect(src).toMatch(/obs-channels|obsChannels|onSetObsChannels/);
    expect(src).not.toMatch(/OBS_LADDER_IDS\.map/);
  });
});

describe("T-128 scenarioAvailability by channels", () => {
  it("scenarioAvailability exports channelAvailability", async () => {
    const mod = await import("./scenarioAvailability");
    expect(mod.channelAvailability).toBeDefined();
    const ch: ObsChannels = {
      pos: "upc_only",
      waste: "none",
      deliveries: "quantity_only",
    };
    expect(mod.channelAvailability("store-spoilage", ch)).toBe("unavailable");
  });
});

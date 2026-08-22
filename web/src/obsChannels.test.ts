/**
 * T-135: ObsChannels global scan model — maskFromChannels parity + UI toggles.
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
  code_type: "upc" | "gsin";
  scan_waste: boolean;
  delivery_history: "none" | "pack_date" | "temperature_history";
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
  arrival_lot_ids: boolean;
  temperature_history: boolean;
};

async function loadObsMask() {
  return (await import("./obsMask")) as {
    maskFromChannels: (ch: ObsChannels) => ObsMask;
    channelsForPreset: (id: string) => ObsChannels;
    channelsCacheKey: (ch: ObsChannels) => string;
  };
}

const ALL_CHANNELS: ObsChannels[] = (["upc", "gsin"] as const).flatMap((code_type) =>
  ([false, true] as const).flatMap((scan_waste) =>
    (["none", "pack_date", "temperature_history"] as const).map(
      (delivery_history) => ({
        code_type,
        scan_waste,
        delivery_history,
      }),
    ),
  ),
);

describe("T-135 maskFromChannels", () => {
  it("covers all twelve orthogonal combos", async () => {
    const { maskFromChannels } = await loadObsMask();
    for (const ch of ALL_CHANNELS) {
      const m = maskFromChannels(ch);
      expect(m.arrivals && m.sales_total).toBe(true);
      expect(m.age_at_receipt).toBe(false);
      if (ch.delivery_history === "pack_date") expect(m.pack_date).toBe(true);
      if (ch.delivery_history === "temperature_history") {
        expect(m.temperature_history).toBe(true);
      }
      if (!ch.scan_waste) expect(m.waste_total).toBe(false);
      if (ch.code_type === "gsin") expect(m.arrival_lot_ids).toBe(true);
    }
  });

  it("F2 preset compiles to pack_date delivery history", async () => {
    const { channelsForPreset, maskFromChannels } = await loadObsMask();
    const ch = channelsForPreset("F2");
    expect(ch.delivery_history).toBe("pack_date");
    const m = maskFromChannels(ch);
    expect(m.pack_date).toBe(true);
    expect(m.age_at_receipt).toBe(false);
  });

  it("F3 preset enables temperature history", async () => {
    const { channelsForPreset, maskFromChannels } = await loadObsMask();
    const ch = channelsForPreset("F3");
    expect(ch.delivery_history).toBe("temperature_history");
    expect(maskFromChannels(ch).temperature_history).toBe(true);
  });
});

describe("T-148 ObsControlsPane toggles", () => {
  it("ObsControlsPane.tsx uses scan-model toggles not ladder chips", () => {
    const src = readSrc("react/ObsControlsPane.tsx");
    expect(src).toMatch(/obs-channels|onSetObsChannels/);
    expect(src).toMatch(/code_type|scan_waste|delivery_history/);
    expect(src).not.toMatch(/OBS_LADDER_IDS\.map/);
  });
});

describe("T-135 scenarioAvailability by channels", () => {
  it("scenarioAvailability exports channelAvailability", async () => {
    const mod = await import("./scenarioAvailability");
    expect(mod.channelAvailability).toBeDefined();
    const ch: ObsChannels = {
      code_type: "upc",
      scan_waste: false,
      delivery_history: "none",
    };
    expect(mod.channelAvailability("store-spoilage", ch)).toBe("unavailable");
  });
});

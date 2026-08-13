/**
 * T-085 RED: Snapshot schedule + demand_summary types and mock stubs (CAL-C1).
 *
 * Studio needs OrderSchedule fields + a chart-ready demand profile summary on
 * cold Snapshot / init without inventing physics in JS.
 */
import { describe, expect, it } from "vitest";
import { MockAdapter } from "../mock/adapter";
import { FORBIDDEN_ENGINE_KEYS, type Snapshot } from "./types";

const DEFAULT_DELIVERY = new Set([0, 2, 4]);
const DEFAULT_ORDER = new Set([6, 1, 3]);
const EPOCH = "2024-01-01";

function collectKeys(value: unknown, found = new Set<string>()): Set<string> {
  if (value !== null && typeof value === "object") {
    if (Array.isArray(value)) {
      for (const item of value) collectKeys(item, found);
    } else {
      for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
        found.add(k);
        collectKeys(v, found);
      }
    }
  }
  return found;
}

function scheduleFromSnapshot(snap: Snapshot): Record<string, unknown> | null {
  const top = (snap as Record<string, unknown>).schedule;
  if (top && typeof top === "object" && !Array.isArray(top)) {
    return top as Record<string, unknown>;
  }
  const applied = snap.applied_config;
  if (applied && typeof applied === "object" && "schedule" in applied) {
    const nested = (applied as Record<string, unknown>).schedule;
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      return nested as Record<string, unknown>;
    }
  }
  return null;
}

function demandSummaryFromSnapshot(
  snap: Snapshot,
): Record<string, unknown> | null {
  const top = (snap as Record<string, unknown>).demand_summary;
  if (top && typeof top === "object" && !Array.isArray(top)) {
    return top as Record<string, unknown>;
  }
  const applied = snap.applied_config;
  if (applied && typeof applied === "object" && "demand_summary" in applied) {
    const nested = (applied as Record<string, unknown>).demand_summary;
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      return nested as Record<string, unknown>;
    }
  }
  return null;
}

function assertSchedule(schedule: Record<string, unknown>, label: string): void {
  const delivery = schedule.delivery_weekdays;
  const order = schedule.order_weekdays;
  const lead = schedule.lead_time_days ?? schedule.lead_time;
  const epoch = schedule.epoch;
  expect(Array.isArray(delivery), `${label}.delivery_weekdays`).toBe(true);
  expect(Array.isArray(order), `${label}.order_weekdays`).toBe(true);
  expect(lead, `${label} lead_time_days`).toBe(1);
  expect(typeof epoch, `${label}.epoch`).toBe("string");
  expect(String(epoch).startsWith(EPOCH), `${label}.epoch`).toBe(true);
  expect(new Set(delivery as number[])).toEqual(DEFAULT_DELIVERY);
  expect(new Set(order as number[])).toEqual(DEFAULT_ORDER);
  for (const d of delivery as number[]) {
    expect(d).toBeGreaterThanOrEqual(0);
    expect(d).toBeLessThanOrEqual(6);
  }
}

function assertDemandSummary(
  summary: Record<string, unknown>,
  label: string,
): void {
  const scale = summary.scale_mu ?? summary.scale_target_mu;
  expect(typeof scale, `${label} scale_mu`).toBe("number");
  expect(Number(scale)).toBeGreaterThan(0);
  const dow = summary.dow_means ?? summary.dow_factors;
  expect(Array.isArray(dow), `${label} dow series`).toBe(true);
  expect(dow as number[]).toHaveLength(7);
  for (const x of dow as number[]) {
    expect(typeof x).toBe("number");
    expect(x).toBeGreaterThan(0);
  }
  expect(summary).not.toHaveProperty("sku_ids");
  expect(summary).not.toHaveProperty("hf_revision");
}

describe("T-085 Snapshot wire types (schedule + demand_summary)", () => {
  it(
    "typespec + tsc require ScheduleWire / DemandSummary on Snapshot",
    async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const { fileURLToPath } = await import("node:url");
    const { spawnSync } = await import("node:child_process");
    const here = path.dirname(fileURLToPath(import.meta.url));
    const webRoot = path.join(here, "..", "..");
    const typespec = path.join(here, "snapshotScheduleDemand.typespec.ts");
    expect(fs.existsSync(typespec)).toBe(true);
    const src = fs.readFileSync(typespec, "utf8");
    expect(src).toMatch(/ScheduleWire/);
    expect(src).toMatch(/DemandSummary/);

    // Prefer local typescript binary (web/ is npm-managed; avoid pnpm bootstrap).
    const tscBin = path.join(webRoot, "node_modules", "typescript", "bin", "tsc");
    const result = spawnSync(tscBin, ["--noEmit", "-p", webRoot], {
      cwd: webRoot,
      encoding: "utf8",
    });
    expect(
      result.status,
      `tsc must accept snapshotScheduleDemand.typespec.ts once ScheduleWire / ` +
        `DemandSummary exist on Snapshot.\nstdout:\n${result.stdout}\nstderr:\n${result.stderr}`,
    ).toBe(0);
    },
    30_000,
  );
});

describe("T-085 MockAdapter schedule + demand_summary stubs", () => {
  it("init Snapshot populates coherent schedule stubs (MWF / LT=1 / SunTueThu)", async () => {
    const adapter = new MockAdapter(42);
    const snap = await adapter.init({});
    const schedule = scheduleFromSnapshot(snap);
    expect(schedule, "MockAdapter Snapshot.schedule").not.toBeNull();
    assertSchedule(schedule!, "mock Snapshot.schedule");
    const keys = collectKeys(snap);
    for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
      expect(keys.has(forbidden)).toBe(false);
    }
  });

  it("init Snapshot populates demand_summary with scale_mu and length-7 DOW series", async () => {
    const adapter = new MockAdapter(42);
    const snap = await adapter.init({});
    const summary = demandSummaryFromSnapshot(snap);
    expect(summary, "MockAdapter Snapshot.demand_summary").not.toBeNull();
    assertDemandSummary(summary!, "mock Snapshot.demand_summary");
  });

  it("reset Snapshot keeps schedule and demand_summary stubs", async () => {
    const adapter = new MockAdapter(42);
    await adapter.init({});
    const snap = await adapter.reset({});
    expect(scheduleFromSnapshot(snap)).not.toBeNull();
    expect(demandSummaryFromSnapshot(snap)).not.toBeNull();
    assertSchedule(scheduleFromSnapshot(snap)!, "reset Snapshot.schedule");
    assertDemandSummary(
      demandSummaryFromSnapshot(snap)!,
      "reset Snapshot.demand_summary",
    );
  });

  it("mock schedule/demand_summary never leak ViewModel or PnL keys", async () => {
    const adapter = new MockAdapter(42);
    const snap = await adapter.init({});
    const keys = collectKeys(snap);
    for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
      expect(keys.has(forbidden)).toBe(false);
    }
    expect(snap).not.toHaveProperty("pnl_series");
    expect(snap).not.toHaveProperty("economics");
  });
});

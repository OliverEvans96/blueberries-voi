/**
 * T-127 RED (qa-wire): EngineAdapter tradeoffForecast + events surface.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { EngineAdapter } from "./adapter";
import { MockAdapter } from "../mock/adapter";
import { WasmAdapter } from "./wasmAdapter";

const HERE = dirname(fileURLToPath(import.meta.url));
const ADAPTER_TS = join(HERE, "adapter.ts");
const WASM_TS = join(HERE, "wasmAdapter.ts");
const MOCK_TS = join(HERE, "../mock/adapter.ts");
const SMOKE_MJS = join(HERE, "../../../scripts/smoke_wasm.mjs");

type TradeoffForecastWire = {
  candidates: {
    q: number;
    waste_mean: number;
    joint_hist: { waste_bins: number[]; missed_bins: number[]; counts: number[][] };
  }[];
};

type EventsWire = { days: { day: number; arrivals: number }[] };

function assertTradeoffMethods(adapter: EngineAdapter): void {
  expect(typeof adapter.tradeoffForecast).toBe("function");
  expect(typeof adapter.events).toBe("function");
}

describe("EngineAdapter wire surface (T-127 AC-wire)", () => {
  it("adapter.ts declares optional tradeoffForecast, slaStockoutCurve, and events", () => {
    const src = readFileSync(ADAPTER_TS, "utf8");
    expect(src).toMatch(/tradeoffForecast\?/);
    expect(src).toMatch(/slaStockoutCurve\?/);
    expect(src).toMatch(/events\?/);
    expect(src).toMatch(/TradeoffForecastWire|tradeoff_forecast/i);
    expect(src).toMatch(/SlaStockoutCurveResult|sla_stockout/i);
    expect(src).toMatch(/EventsWire|since_day/);
  });

  it("wasmAdapter.ts implements tradeoffForecast and slaStockoutCurve via handle_rpc", () => {
    const src = readFileSync(WASM_TS, "utf8");
    expect(src).toMatch(/tradeoffForecast/);
    expect(src).toMatch(/tradeoff_forecast/);
    expect(src).toMatch(/slaStockoutCurve/);
    expect(src).toMatch(/sla_stockout_curve/);
    expect(src).toMatch(/events/);
  });

  it("mockAdapter.ts returns deterministic fixtures", async () => {
    const src = readFileSync(MOCK_TS, "utf8");
    expect(src).toMatch(/tradeoffForecast/);
    expect(src).toMatch(/slaStockoutCurve/);
    expect(src).toMatch(/events/);
    const mock = new MockAdapter();
    assertTradeoffMethods(mock);
    expect(typeof mock.slaStockoutCurve).toBe("function");
    const sla = await mock.slaStockoutCurve!();
    expect(sla.candidates.length).toBeGreaterThan(0);
    expect(sla.candidates[0]!.p_stockout).toBeDefined();
    const tf = (await mock.tradeoffForecast!()) as TradeoffForecastWire;
    expect(tf.candidates.length).toBeGreaterThan(0);
    expect(tf.candidates[0]!.joint_hist).toBeDefined();
    const ev = (await mock.events!({ since_day: 0 })) as EventsWire;
    expect(Array.isArray(ev.days)).toBe(true);
  });

  it("mock tradeoffForecast reacts to episode advance and obs channel switch", async () => {
    const mock = new MockAdapter(42);
    await mock.init({});
    const before = (await mock.tradeoffForecast!()) as TradeoffForecastWire;
    await mock.step(16);
    const afterAdvance = (await mock.tradeoffForecast!()) as TradeoffForecastWire;
    expect(afterAdvance.candidates[1]!.waste_mean).not.toBe(
      before.candidates[1]!.waste_mean,
    );
    await mock.set_obs_channels({
      code_type: "gsin",
      scan_waste: true,
      delivery_history: "pack_date",
    });
    const afterChannels = (await mock.tradeoffForecast!()) as TradeoffForecastWire;
    expect(afterChannels.candidates[1]!.waste_mean).not.toBe(
      afterAdvance.candidates[1]!.waste_mean,
    );
  });

  it("WasmAdapter class exposes tradeoffForecast, slaStockoutCurve, and events methods", () => {
    const src = readFileSync(WASM_TS, "utf8");
    expect(src).toMatch(/async tradeoffForecast/);
    expect(src).toMatch(/async slaStockoutCurve/);
    expect(src).toMatch(/async events/);
  });

  it("smoke_wasm.mjs calls tradeoff_forecast and events after init+step", () => {
    const src = readFileSync(SMOKE_MJS, "utf8");
    expect(src).toMatch(/tradeoff_forecast/);
    expect(src).toMatch(/events/);
    expect(src).toMatch(/joint_hist/);
    expect(src).toMatch(/since_day/);
  });

  it("events envelope is { days: [...] } per qa-wire lock", () => {
    const src = readFileSync(ADAPTER_TS, "utf8");
    expect(src).toMatch(/days\s*:/);
  });
});

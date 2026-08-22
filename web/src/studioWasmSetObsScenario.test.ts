/**
 * T-114 RED: wasm adapter + mock 90-day refuse + worker RPC set_obs_scenario.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MockAdapter } from "./mock/adapter";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_SRC = HERE;
const WASM_ADAPTER = join(HERE, "engine/wasmAdapter.ts");
const WASM_WORKER = join(HERE, "engine/wasmWorker.ts");

describe("T-114 WasmAdapter forwards set_obs_scenario", () => {
  it("wasmAdapter.ts mentions set_obs_scenario", () => {
    const src = readFileSync(WASM_ADAPTER, "utf8");
    expect(src).toMatch(/set_obs_scenario/);
  });

  it("wasmWorker.ts lists set_obs_scenario with other RPC methods", () => {
    const src = readFileSync(WASM_WORKER, "utf8");
    expect(src).toMatch(/set_obs_scenario/);
    expect(src).toMatch(/init/);
    expect(src).toMatch(/act/);
  });
});

describe("T-114 mock adapter refuses at day 90", () => {
  it("step throws Reset copy after 90 days", async () => {
    const adapter = new MockAdapter(1);
    await adapter.init({});
    for (let i = 0; i < 90; i++) {
      await adapter.step(0);
    }
    await expect(adapter.step(0)).rejects.toThrow(/episode|horizon/i);
    await expect(adapter.step(0)).rejects.toThrow(/Reset/i);
  });
});

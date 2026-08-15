/**
 * T-125 RED: WASM-default studio adapter (ADR 0129).
 *
 * StudioAdapterKind is "wasm" | "mock" only; resolveStudioAdapterKind defaults to wasm.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  resolveStudioAdapterKind,
  type StudioAdapterKind,
  type StudioEnv,
} from "./studioAdapter";

const HERE = dirname(fileURLToPath(import.meta.url));
const STUDIO_ADAPTER_TS = join(HERE, "studioAdapter.ts");

describe("T-125 resolveStudioAdapterKind defaults to wasm", () => {
  it("returns wasm when VITE_ENGINE_ADAPTER is unset", () => {
    expect(resolveStudioAdapterKind({})).toBe("wasm");
  });

  it("returns wasm in production when override is unset (not pyodide)", () => {
    const prod: StudioEnv = { MODE: "production", PROD: true };
    expect(resolveStudioAdapterKind(prod)).toBe("wasm");
  });

  it("returns wasm in dev when API base is configured (not http)", () => {
    const dev: StudioEnv = {
      MODE: "development",
      DEV: true,
      VITE_ENGINE_API_BASE_URL: "http://127.0.0.1:8000",
    };
    expect(resolveStudioAdapterKind(dev)).toBe("wasm");
  });

  it("still honors explicit mock override", () => {
    expect(resolveStudioAdapterKind({ VITE_ENGINE_ADAPTER: "mock" })).toBe(
      "mock",
    );
  });

  it("still honors explicit wasm override", () => {
    expect(resolveStudioAdapterKind({ VITE_ENGINE_ADAPTER: "wasm" })).toBe(
      "wasm",
    );
  });
});

describe("T-125 StudioAdapterKind is wasm | mock only", () => {
  it("studioAdapter.ts type union is wasm | mock (no http or pyodide)", () => {
    const src = readFileSync(STUDIO_ADAPTER_TS, "utf8");
    expect(src).toMatch(
      /StudioAdapterKind\s*=\s*["']wasm["']\s*\|\s*["']mock["']/,
    );
    expect(src).not.toMatch(/StudioAdapterKind[\s\S]*?["']http["']/);
    expect(src).not.toMatch(/StudioAdapterKind[\s\S]*?["']pyodide["']/);
  });

  it("createStudioAdapter has no http or pyodide branches", () => {
    const src = readFileSync(STUDIO_ADAPTER_TS, "utf8");
    expect(src).not.toMatch(/kind\s*===\s*["']http["']/);
    expect(src).not.toMatch(/kind\s*===\s*["']pyodide["']/);
    expect(src).not.toMatch(/from\s+["']\.\/httpAdapter["']/);
    expect(src).not.toMatch(/from\s+["']\.\/pyodideAdapter["']/);
  });

  it("resolveStudioAdapterKind never returns http or pyodide for any env", () => {
    const envs: StudioEnv[] = [
      {},
      { MODE: "production", PROD: true },
      { MODE: "development", DEV: true },
      {
        MODE: "development",
        DEV: true,
        VITE_ENGINE_API_BASE_URL: "http://127.0.0.1:8000",
      },
      { VITE_ENGINE_ADAPTER: "mock" },
      { VITE_ENGINE_ADAPTER: "wasm" },
    ];
    const allowed: StudioAdapterKind[] = ["wasm", "mock"];
    for (const env of envs) {
      const kind = resolveStudioAdapterKind(env);
      expect(kind).not.toBe("http");
      expect(kind).not.toBe("pyodide");
      expect(allowed).toContain(kind);
    }
  });
});

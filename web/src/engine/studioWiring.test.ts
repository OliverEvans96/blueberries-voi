/**
 * T-057 / T-125 RED: wire D3 studio — WASM-only default (WasmAdapter);
 * fake generate.ts physics off the default path; setEconomics stays local.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EngineAdapter } from "./adapter";
import { MockAdapter } from "../mock/adapter";
import { WasmAdapter } from "./wasmAdapter";
import { ViewModelProjector } from "./projector";
import {
  createStudioAdapter,
  resetBundledWasmAdapterForTests,
  resolveStudioAdapterKind,
  type StudioEnv,
} from "./studioAdapter";
import { DEFAULT_ECONOMICS } from "../mock/generate";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(HERE, "../..");
const REPO_ROOT = join(WEB_ROOT, "..");
const MAIN_TS = join(WEB_ROOT, "src/react/studioLogic.ts");
const STUDIO_ADAPTER_TS = join(HERE, "studioAdapter.ts");

class FakeWorker {
  static instances: FakeWorker[] = [];
  url: string | URL;
  posted: unknown[] = [];
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: ErrorEvent) => void) | null = null;

  constructor(url: string | URL, _opts?: WorkerOptions) {
    this.url = url;
    FakeWorker.instances.push(this);
  }

  postMessage(data: unknown): void {
    this.posted.push(data);
  }

  terminate(): void {
    /* no-op */
  }

  addEventListener(
    type: string,
    listener: EventListenerOrEventListenerObject,
  ): void {
    if (type === "message") {
      this.onmessage = listener as (ev: MessageEvent) => void;
    }
    if (type === "error") {
      this.onerror = listener as (ev: ErrorEvent) => void;
    }
  }

  removeEventListener(): void {
    /* no-op */
  }
}

function installFakeWorker(): void {
  FakeWorker.instances = [];
  vi.stubGlobal(
    "Worker",
    class extends FakeWorker {
      constructor(url: string | URL, opts?: WorkerOptions) {
        super(url, opts);
      }
    },
  );
}

const DEV_ENV: StudioEnv = {
  MODE: "development",
  DEV: true,
  PROD: false,
  VITE_ENGINE_API_BASE_URL: "http://127.0.0.1:8000",
};

const PROD_ENV: StudioEnv = {
  MODE: "production",
  DEV: false,
  PROD: true,
};

describe("T-125 studio adapter selection (wasm default)", () => {
  beforeEach(() => {
    resetBundledWasmAdapterForTests();
    installFakeWorker();
  });
  afterEach(() => {
    resetBundledWasmAdapterForTests();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("dev build with API base URL still resolves to wasm kind", () => {
    expect(resolveStudioAdapterKind(DEV_ENV)).toBe("wasm");
  });

  it("prod/demo build resolves to wasm kind (not pyodide)", () => {
    expect(resolveStudioAdapterKind(PROD_ENV)).toBe("wasm");
  });

  it("explicit VITE_ENGINE_ADAPTER=mock keeps Mock as a debug option", () => {
    expect(
      resolveStudioAdapterKind({
        ...PROD_ENV,
        VITE_ENGINE_ADAPTER: "mock",
      }),
    ).toBe("mock");
  });

  it("explicit VITE_ENGINE_ADAPTER=wasm selects wasm", () => {
    expect(
      resolveStudioAdapterKind({
        ...PROD_ENV,
        VITE_ENGINE_ADAPTER: "wasm",
      }),
    ).toBe("wasm");
  });

  it("wasm Init does not load the Pyodide worker even if that URL is passed", () => {
    const adapter = createStudioAdapter({
      env: {
        ...PROD_ENV,
        VITE_ENGINE_ADAPTER: "wasm",
      },
      workerUrl: "/packaging/pyodide/worker.js",
    });
    expect(adapter).toBeInstanceOf(WasmAdapter);
    expect(FakeWorker.instances.length).toBeGreaterThanOrEqual(1);
    const urlStr = String(FakeWorker.instances[0]!.url);
    expect(urlStr).toMatch(/wasmWorker\.ts/);
    expect(urlStr).not.toMatch(/pyodide/);
    expect(urlStr).not.toMatch(/github\.com\/oliver/);
  });

  it("createStudioAdapter builds WasmAdapter for dev default kind", () => {
    const adapter = createStudioAdapter({
      env: DEV_ENV,
    });
    expect(adapter).toBeInstanceOf(WasmAdapter);
    expect(typeof (adapter as EngineAdapter).init).toBe("function");
    expect(typeof (adapter as EngineAdapter).step).toBe("function");
    expect(FakeWorker.instances.length).toBeGreaterThanOrEqual(1);
    const urlStr = String(FakeWorker.instances[0]!.url);
    expect(urlStr).toMatch(/wasmWorker\.ts/);
    expect(urlStr).not.toMatch(/pyodide/);
  });

  it("createStudioAdapter builds WasmAdapter for prod default kind", () => {
    const adapter = createStudioAdapter({
      env: PROD_ENV,
    });
    expect(adapter).toBeInstanceOf(WasmAdapter);
    expect(FakeWorker.instances.length).toBeGreaterThanOrEqual(1);
    const urlStr = String(FakeWorker.instances[0]!.url);
    expect(urlStr).toMatch(/wasmWorker\.ts/);
    expect(urlStr).not.toMatch(/pyodide/);
  });

  it("createStudioAdapter builds MockAdapter only when kind is mock", () => {
    const adapter = createStudioAdapter({
      kind: "mock",
      env: PROD_ENV,
    });
    expect(adapter).toBeInstanceOf(MockAdapter);
  });
});

describe("T-057 studio chrome wires projector + selected adapter", () => {
  it("react/studioLogic.ts constructs the studio adapter via createStudioAdapter (not bare MockAdapter default)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/createStudioAdapter/);
    // Unconditional `new MockAdapter()` is the pre-T-057 default path — must go.
    expect(src).not.toMatch(/const\s+adapter\s*=\s*new\s+MockAdapter\s*\(/);
  });

  it("react/studioLogic.ts selects adapters via studioAdapter helper (no Http/Pyodide imports)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/from\s+["'](\.\.\/|\.\/)engine\/studioAdapter["']/);
    expect(src).not.toMatch(/from\s+["']\.\/engine\/httpAdapter["']/);
    expect(src).not.toMatch(/from\s+["']\.\/engine\/pyodideAdapter["']/);
    expect(src).not.toMatch(/\bHttpAdapter\b/);
    expect(src).not.toMatch(/\bPyodideAdapter\b/);
  });

  it("Advance / Reset / bootstrap go through adapter.step_n (primary) / reset / init + projector", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    // T-086 / CAL-C2: primary play advances via step_n to the next order day.
    expect(src).toMatch(/adapter\.step_n\s*\(/);
    expect(src).toMatch(/adapter\.reset\s*\(/);
    // Bootstrap uses sharedBundledWasmInit → adapter.init(config).
    expect(src).toMatch(/sharedBundledWasmInit\s*\(\s*adapter\s*,/);
    expect(src).toMatch(/projector\.applyDelta/);
    expect(src).toMatch(/projector\.applySnapshot/);
    // Must not call the fake day-loop generator from the studio chrome path.
    expect(src).not.toMatch(/stepSimulation\s*\(/);
    expect(src).not.toMatch(/from\s+["']\.\/mock\/generate["']/);
  });

  it("economics sliders call projector.setEconomics only (no adapter / network)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/projector\.setEconomics\s*\(/);
    expect(src).not.toMatch(/adapter\.setEconomics/);
    // Economics must not POST / RPC from the chrome handler.
    const economicsHandler = src.match(
      /onEconomicsChange\s*\([^)]*\)\s*\{[\s\S]*?\n\s*\},/,
    );
    expect(economicsHandler, "expected onEconomicsChange handler in react/studioLogic.ts").toBeTruthy();
    const body = economicsHandler![0]!;
    expect(body).toMatch(/projector\.setEconomics/);
    expect(body).not.toMatch(/\bfetch\s*\(/);
    expect(body).not.toMatch(/\.postMessage\s*\(/);
    expect(body).not.toMatch(/adapter\.(init|step|reset|act)\s*\(/);
  });

  it("obs channel handler uses patchEngineState (not applySnapshot)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/async function applyObsSelection/);
    const start = src.indexOf("async function applyObsSelection");
    const body = src.slice(start, start + 1200);
    expect(body).toMatch(/projector\.patchEngineState\s*\(/);
    expect(body).not.toMatch(/projector\.applySnapshot\s*\(/);
  });
});

describe("T-125 default path leaves fake generate.ts physics", () => {
  it("studioAdapter default (no explicit mock) is WasmAdapter not MockAdapter", () => {
    resetBundledWasmAdapterForTests();
    installFakeWorker();
    try {
      const prod = createStudioAdapter({
        env: PROD_ENV,
      });
      expect(prod).toBeInstanceOf(WasmAdapter);
      expect(prod).not.toBeInstanceOf(MockAdapter);

      const dev = createStudioAdapter({
        env: DEV_ENV,
      });
      expect(dev).toBeInstanceOf(WasmAdapter);
      expect(dev).not.toBeInstanceOf(MockAdapter);
    } finally {
      resetBundledWasmAdapterForTests();
      vi.unstubAllGlobals();
    }
  });

  it("resolveStudioAdapterKind never silently defaults to mock without override", () => {
    expect(resolveStudioAdapterKind(DEV_ENV)).not.toBe("mock");
    expect(resolveStudioAdapterKind(PROD_ENV)).not.toBe("mock");
  });

  it("studioAdapter module wires WasmAdapter only (no http/pyodide imports)", () => {
    const src = readFileSync(STUDIO_ADAPTER_TS, "utf8");
    expect(src).not.toMatch(/stepSimulation/);
    expect(src).not.toMatch(/createInitialState/);
    expect(src).toMatch(/from\s+["']\.\/wasmAdapter["']/);
    expect(src).not.toMatch(/from\s+["']\.\/httpAdapter["']/);
    expect(src).not.toMatch(/from\s+["']\.\/pyodideAdapter["']/);
  });
});

describe("T-057 setEconomics remains local via projector", () => {
  it("ViewModelProjector.setEconomics does not require an EngineAdapter", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 14,
    });
    const before = projector.getViewModel();
    const after = projector.setEconomics({
      ...DEFAULT_ECONOMICS,
      price: DEFAULT_ECONOMICS.price + 1,
    });
    expect(after.economics.price).toBe(DEFAULT_ECONOMICS.price + 1);
    expect(after).not.toBe(before);
  });
});

describe("T-057 smoke checklist recorded", () => {
  it("ships a dedicated smoke checklist under .team/qa/ or mockup README", () => {
    // Dedicated artifact only — do not treat RED qa status notes as the checklist.
    const candidates = [
      join(REPO_ROOT, ".team/qa/T-057-smoke.md"),
      join(REPO_ROOT, ".team/qa/T-057-checklist.md"),
      join(WEB_ROOT, "README.md"),
      join(WEB_ROOT, "SMOKE.md"),
      join(WEB_ROOT, "docs/smoke.md"),
    ];
    const hit = candidates.find((p) => existsSync(p));
    expect(
      hit,
      "expected .team/qa/T-057-smoke.md (or mockup README) documenting adapter smoke",
    ).toBeTruthy();
    const text = readFileSync(hit!, "utf8");
    expect(text).toMatch(/WasmAdapter|wasm/i);
    expect(text).not.toMatch(/PyodideAdapter|pyodide/i);
    expect(text).not.toMatch(/HttpAdapter|http\s+studio/i);
    expect(text).toMatch(/smoke|checklist|pass\s*\/\s*fail/i);
  });
});

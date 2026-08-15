/**
 * T-057 RED: wire D3 studio — prod=PyodideAdapter, dev=HttpAdapter;
 * fake generate.ts physics off the default path; setEconomics stays local.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EngineAdapter } from "./adapter";
import { HttpAdapter } from "./httpAdapter";
import { MockAdapter } from "../mock/adapter";
import { PyodideAdapter } from "./pyodideAdapter";
import { WasmAdapter } from "./wasmAdapter";
import { ViewModelProjector } from "./projector";
import {
  createStudioAdapter,
  resolveStudioAdapterKind,
  type StudioEnv,
} from "./studioAdapter";
import { DEFAULT_ECONOMICS } from "../mock/generate";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(HERE, "../..");
const REPO_ROOT = join(WEB_ROOT, "..");
const MAIN_TS = join(WEB_ROOT, "src/main.ts");
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
  VITE_PYODIDE_WORKER_URL: "/worker.js",
  VITE_PYODIDE_WHEEL_URL:
    "https://example.test/blueberries_voi-0.1.0-py3-none-any.whl",
};

describe("T-057 studio adapter selection (dev=HTTP, prod=Pyodide)", () => {
  beforeEach(() => {
    installFakeWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("dev build with API base URL resolves to HttpAdapter kind", () => {
    expect(resolveStudioAdapterKind(DEV_ENV)).toBe("http");
  });

  it("prod/demo build resolves to PyodideAdapter kind", () => {
    expect(resolveStudioAdapterKind(PROD_ENV)).toBe("pyodide");
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
    expect(urlStr).toMatch(/packaging\/wasm\/worker\.js/);
    expect(urlStr).not.toMatch(/pyodide/);
    expect(urlStr).not.toMatch(/github\.com\/oliver/);
  });

  it("explicit VITE_ENGINE_ADAPTER=http selects http", () => {
    expect(
      resolveStudioAdapterKind({
        ...PROD_ENV,
        VITE_ENGINE_ADAPTER: "http",
        VITE_ENGINE_API_BASE_URL: "http://127.0.0.1:8000",
      }),
    ).toBe("http");
  });

  it("createStudioAdapter builds HttpAdapter for dev/http kind", () => {
    const adapter = createStudioAdapter({
      env: DEV_ENV,
      baseUrl: DEV_ENV.VITE_ENGINE_API_BASE_URL,
      fetch: vi.fn() as unknown as typeof fetch,
    });
    expect(adapter).toBeInstanceOf(HttpAdapter);
    expect(typeof (adapter as EngineAdapter).init).toBe("function");
    expect(typeof (adapter as EngineAdapter).step).toBe("function");
  });

  it("createStudioAdapter builds PyodideAdapter for prod/pyodide kind", () => {
    const adapter = createStudioAdapter({
      env: PROD_ENV,
      workerUrl: PROD_ENV.VITE_PYODIDE_WORKER_URL,
      wheelUrl: PROD_ENV.VITE_PYODIDE_WHEEL_URL,
    });
    expect(adapter).toBeInstanceOf(PyodideAdapter);
    expect(FakeWorker.instances.length).toBeGreaterThanOrEqual(1);
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
  it("main.ts constructs the studio adapter via createStudioAdapter (not bare MockAdapter default)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/createStudioAdapter/);
    // Unconditional `new MockAdapter()` is the pre-T-057 default path — must go.
    expect(src).not.toMatch(/const\s+adapter\s*=\s*new\s+MockAdapter\s*\(/);
  });

  it("main.ts imports HttpAdapter and PyodideAdapter selection (or studioAdapter helper)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    const usesHelper = /from\s+["']\.\/engine\/studioAdapter["']/.test(src);
    const importsBoth =
      /HttpAdapter/.test(src) && /PyodideAdapter/.test(src);
    expect(
      usesHelper || importsBoth,
      "main must select adapters via studioAdapter helper or direct Http/Pyodide imports",
    ).toBe(true);
  });

  it("Advance / Reset / bootstrap go through adapter.step_n (primary) / reset / init + projector", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    // T-086 / CAL-C2: primary play advances via step_n to the next order day.
    expect(src).toMatch(/adapter\.step_n\s*\(/);
    expect(src).toMatch(/adapter\.reset\s*\(/);
    expect(src).toMatch(/adapter\.init\s*\(/);
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
    expect(economicsHandler, "expected onEconomicsChange handler in main.ts").toBeTruthy();
    const body = economicsHandler![0]!;
    expect(body).toMatch(/projector\.setEconomics/);
    expect(body).not.toMatch(/\bfetch\s*\(/);
    expect(body).not.toMatch(/\.postMessage\s*\(/);
    expect(body).not.toMatch(/adapter\.(init|step|reset|act)\s*\(/);
  });
});

describe("T-057 default path leaves fake generate.ts physics", () => {
  it("studioAdapter default (no explicit mock) is not MockAdapter", () => {
    installFakeWorker();
    try {
      const prod = createStudioAdapter({
        env: PROD_ENV,
        workerUrl: PROD_ENV.VITE_PYODIDE_WORKER_URL,
        wheelUrl: PROD_ENV.VITE_PYODIDE_WHEEL_URL,
      });
      expect(prod).not.toBeInstanceOf(MockAdapter);

      const dev = createStudioAdapter({
        env: DEV_ENV,
        baseUrl: DEV_ENV.VITE_ENGINE_API_BASE_URL,
        fetch: vi.fn() as unknown as typeof fetch,
      });
      expect(dev).not.toBeInstanceOf(MockAdapter);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("resolveStudioAdapterKind never silently defaults to mock without override", () => {
    expect(resolveStudioAdapterKind(DEV_ENV)).not.toBe("mock");
    expect(resolveStudioAdapterKind(PROD_ENV)).not.toBe("mock");
  });

  it("studioAdapter module does not import generate.ts day-loop helpers for defaults", () => {
    const src = readFileSync(STUDIO_ADAPTER_TS, "utf8");
    expect(src).not.toMatch(/stepSimulation/);
    expect(src).not.toMatch(/createInitialState/);
    // Default path must construct real adapters (imports, not comments alone).
    expect(src).toMatch(/from\s+["']\.\/httpAdapter["']/);
    expect(src).toMatch(/from\s+["']\.\/pyodideAdapter["']/);
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
    expect(text).toMatch(/HttpAdapter|http/i);
    expect(text).toMatch(/PyodideAdapter|pyodide/i);
    expect(text).toMatch(/smoke|checklist|pass\s*\/\s*fail/i);
  });
});

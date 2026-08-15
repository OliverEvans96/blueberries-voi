/**
 * T-074 / T-125 RED: studio footer, WASM local env defaults, live-adapter errors (ADR 0129).
 *
 * Static + unit contracts. Does not start Vite or the ASGI API.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockAdapter } from "../mock/adapter";
import { WasmAdapter } from "./wasmAdapter";
import {
  createStudioAdapter,
  resolveStudioAdapterKind,
  studioFooterCopy,
  resolveLocalStudioDefaults,
  reportStudioAdapterError,
  type StudioEnv,
} from "./studioAdapter";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(HERE, "../..");
const MAIN_TS = join(WEB_ROOT, "src/react/studioLogic.ts");
const STUDIO_ADAPTER_TS = join(HERE, "studioAdapter.ts");

class FakeWorker {
  static instances: FakeWorker[] = [];
  readonly url: string | URL;

  constructor(url: string | URL, _opts?: WorkerOptions) {
    this.url = url;
    FakeWorker.instances.push(this);
  }

  postMessage(): void {
    /* no-op */
  }

  terminate(): void {
    /* no-op */
  }

  addEventListener(): void {
    /* no-op */
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

describe("T-125 studio footer for live WASM adapter", () => {
  it("studioFooterCopy(wasm) does not claim fake or mock data", () => {
    const copy = studioFooterCopy("wasm");
    expect(copy.length).toBeGreaterThan(0);
    expect(copy).toMatch(/WASM/i);
    expect(copy).not.toMatch(/fake\s+data/i);
    expect(copy).not.toMatch(/\bmock\b/i);
    expect(copy).not.toMatch(/Pyodide/i);
    expect(copy).not.toMatch(/HTTP/i);
  });

  it("studioFooterCopy has no http or pyodide branches", () => {
    const src = readFileSync(STUDIO_ADAPTER_TS, "utf8");
    const fn = src.match(/function studioFooterCopy[\s\S]*?\n\}/);
    expect(fn, "expected studioFooterCopy in studioAdapter.ts").toBeTruthy();
    const body = fn![0]!;
    expect(body).toMatch(/kind\s*===\s*["']wasm["']/);
    expect(body).not.toMatch(/kind\s*===\s*["']http["']/);
    expect(body).not.toMatch(/kind\s*===\s*["']pyodide["']/);
  });

  it("react/studioLogic.ts footer is driven by adapter kind (no hardcoded Fake data studio for live path)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/studioFooterCopy|footerCopy|studioFooter/);
    // Unconditional template claim must go for live Http/Pyodide readiness.
    expect(src).not.toMatch(/Fake data studio · blueberries-voi/);
  });
});

describe("T-125 local env defaults (WASM worker + pkg)", () => {
  beforeEach(() => {
    installFakeWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("resolveLocalStudioDefaults exposes WASM worker + pkg URLs (not pyodide wheel)", () => {
    const defaults = resolveLocalStudioDefaults();
    expect(defaults.workerUrl).toMatch(/packaging\/wasm\/worker\.js/);
    expect(defaults.workerUrl).not.toMatch(/pyodide/);
    expect(defaults.wheelUrl).toMatch(/\/wasm\//);
    expect(defaults.wheelUrl).not.toMatch(/\/wheels\/.+\.whl/);
    expect(defaults.wheelUrl).not.toMatch(/github\.com\/oliver\//);
  });

  it("createStudioAdapter wasm defaults use local WASM worker + pkg URLs", () => {
    createStudioAdapter({
      env: { MODE: "production", PROD: true },
    });
    expect(FakeWorker.instances.length).toBeGreaterThanOrEqual(1);
    const urlStr = decodeURIComponent(String(FakeWorker.instances[0]!.url));
    expect(urlStr).toMatch(/packaging\/wasm\/worker\.js/);
    expect(urlStr).toMatch(/pkgUrl=/);
    expect(urlStr).not.toMatch(/pyodide/);
    expect(urlStr).not.toMatch(/\/wheels\/.+\.whl|wheelUrl=/);
    expect(urlStr).not.toMatch(/github\.com\/oliver\//);
  });

  it("documents WASM defaults via .env.example or studioAdapter contract constants", () => {
    const envCandidates = [
      join(WEB_ROOT, ".env.example"),
      join(WEB_ROOT, ".env.development"),
      join(WEB_ROOT, ".env.local.example"),
    ];
    const envHit = envCandidates.find((p) => existsSync(p));
    const adapterSrc = readFileSync(STUDIO_ADAPTER_TS, "utf8");
    const hasCodeDefaults =
      /packaging\/wasm\/worker\.js/.test(adapterSrc) &&
      /\/wasm\//.test(adapterSrc) &&
      !/DEFAULT_PYODIDE_WHEEL_URL/.test(adapterSrc);
    if (envHit) {
      const text = readFileSync(envHit, "utf8");
      expect(text).toMatch(/VITE_WASM_WORKER_URL|VITE_WASM_PKG_URL/);
      expect(text).not.toMatch(/VITE_PYODIDE_WORKER_URL|VITE_PYODIDE_WHEEL_URL/);
      expect(text).not.toMatch(
        /VITE_PYODIDE_WHEEL_URL\s*=\s*https:\/\/github\.com\/oliver\//,
      );
    }
    expect(
      envHit || hasCodeDefaults,
      "need .env.example (or equiv) or code defaults with WASM worker + /wasm pkg",
    ).toBeTruthy();
  });
});

describe("T-074 adapter init/step errors surface to the user", () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    errorSpy.mockRestore();
  });

  it("reportStudioAdapterError writes a non-empty visible message on a target", () => {
    // Node vitest harness: pass a minimal element-like target (no jsdom required).
    const target = { textContent: "", hidden: true };
    reportStudioAdapterError("init failed: connection refused", target);
    expect(target.textContent).toMatch(/init failed|connection refused/i);
    expect(target.hidden).toBe(false);
  });

  it("reportStudioAdapterError console.errors a prefix plus the original Error (traceback inspectable)", () => {
    const target = { textContent: "", hidden: true };
    const err = new Error(
      "PythonError: Traceback (most recent call last):\n  File \"<exec>\", line 1",
    );
    reportStudioAdapterError(`Init failed: ${err.message}`, target, err);
    expect(target.textContent).toMatch(/Init failed|Traceback/i);
    expect(target.hidden).toBe(false);
    expect(errorSpy).toHaveBeenCalled();
    const args = errorSpy.mock.calls[0]!;
    expect(String(args[0])).toMatch(/Studio init failed/i);
    expect(args).toContain(err);
  });

  it("reportStudioAdapterError still console.errors when only a message is given", () => {
    const target = { textContent: "", hidden: true };
    reportStudioAdapterError("init failed: connection refused", target);
    expect(errorSpy).toHaveBeenCalled();
    const joined = errorSpy.mock.calls[0]!.map(String).join(" ");
    expect(joined).toMatch(/Studio|init failed|connection refused/i);
  });

  it("react/studioLogic.ts catches adapter init/step failures and surfaces them (non-silent)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/reportStudioAdapterError|studio-error|surfaceAdapter/);
    // bootstrap / Advance / Reset must not swallow rejections without catch.
    expect(src).toMatch(/catch\s*\(/);
    const bootstrap = src.match(/async function bootstrap[\s\S]*?\n\}/);
    expect(bootstrap, "expected bootstrap() in react/studioLogic.ts").toBeTruthy();
    expect(bootstrap![0]).toMatch(/catch|reportStudioAdapterError/);
    // Advance may use step_n (CAL-01 next-order-day) with a longer try body.
    expect(src).toMatch(
      /onAdvance[\s\S]{0,1200}catch|adapter\.step(?:_n)?[\s\S]{0,400}catch/,
    );
  });

  it("react/studioLogic.ts passes the original err into reportStudioAdapterError (banner + console)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    const calls = [...src.matchAll(/reportStudioAdapterError\(([^;]+)\)/g)];
    expect(calls.length).toBeGreaterThanOrEqual(4);
    for (const call of calls) {
      // Cause must be a separate argument (not only interpolated into the banner string).
      expect(call[1]).toMatch(/,\s*err\s*,?\s*$/);
    }
  });
});

describe("T-125 MockAdapter only when VITE_ENGINE_ADAPTER=mock", () => {
  beforeEach(() => {
    installFakeWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("resolveStudioAdapterKind is mock only for explicit override", () => {
    expect(resolveStudioAdapterKind({ VITE_ENGINE_ADAPTER: "mock" })).toBe(
      "mock",
    );
    const liveEnvs: StudioEnv[] = [
      { MODE: "development", DEV: true, VITE_ENGINE_API_BASE_URL: "http://127.0.0.1:8000" },
      { MODE: "production", PROD: true },
      { MODE: "development", DEV: true },
      { VITE_ENGINE_ADAPTER: "wasm" },
    ];
    for (const env of liveEnvs) {
      expect(resolveStudioAdapterKind(env)).not.toBe("mock");
    }
  });

  it("createStudioAdapter returns MockAdapter only for mock kind / env", () => {
    const mock = createStudioAdapter({
      env: { VITE_ENGINE_ADAPTER: "mock" },
    });
    expect(mock).toBeInstanceOf(MockAdapter);

    const wasm = createStudioAdapter({
      env: { MODE: "production", PROD: true },
    });
    expect(wasm).toBeInstanceOf(WasmAdapter);
    expect(wasm).not.toBeInstanceOf(MockAdapter);
  });

  it("default readiness path resolves to wasm and does not silently fall back to mock", () => {
    const kind = resolveStudioAdapterKind({
      MODE: "development",
      DEV: true,
    });
    expect(kind).toBe("wasm");
    expect(kind).not.toBe("mock");
    const adapter = createStudioAdapter({
      env: { MODE: "development", DEV: true },
    });
    expect(adapter).toBeInstanceOf(WasmAdapter);
    expect(adapter).not.toBeInstanceOf(MockAdapter);
  });
});

/**
 * T-074 RED: studio footer, local env defaults, live-adapter errors (ADR 0108).
 *
 * Static + unit contracts. Does not start Vite or the ASGI API.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockAdapter } from "../mock/adapter";
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
const MAIN_TS = join(WEB_ROOT, "src/main.ts");
const STUDIO_ADAPTER_TS = join(HERE, "studioAdapter.ts");
const LOCAL_WHEEL_PATH =
  "/wheels/blueberries_voi-0.1.0-py3-none-any.whl";
const LOCAL_WORKER_PATH = "/packaging/pyodide/worker.js";

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

describe("T-074 studio footer for live adapters", () => {
  it("studioFooterCopy(http) does not claim fake or mock data", () => {
    const copy = studioFooterCopy("http");
    expect(copy.length).toBeGreaterThan(0);
    expect(copy).not.toMatch(/fake\s+data/i);
    expect(copy).not.toMatch(/\bmock\b/i);
  });

  it("studioFooterCopy(pyodide) does not claim fake or mock data", () => {
    const copy = studioFooterCopy("pyodide");
    expect(copy.length).toBeGreaterThan(0);
    expect(copy).not.toMatch(/fake\s+data/i);
    expect(copy).not.toMatch(/\bmock\b/i);
  });

  it("main.ts footer is driven by adapter kind (no hardcoded Fake data studio for live path)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/studioFooterCopy|footerCopy|studioFooter/);
    // Unconditional template claim must go for live Http/Pyodide readiness.
    expect(src).not.toMatch(/Fake data studio · blueberries-voi/);
  });
});

describe("T-074 local env defaults (API + worker + wheel)", () => {
  beforeEach(() => {
    installFakeWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("resolveLocalStudioDefaults exposes localhost API base for HTTP readiness", () => {
    const defaults = resolveLocalStudioDefaults();
    expect(defaults.apiBaseUrl).toMatch(/^(https?:\/\/)?(localhost|127\.0\.0\.1)(:\d+)?/);
  });

  it("resolveLocalStudioDefaults uses local worker + local wheel (not github.com/oliver only)", () => {
    const defaults = resolveLocalStudioDefaults();
    expect(defaults.workerUrl).toMatch(/packaging\/pyodide\/worker\.js|\/worker\.js/);
    expect(defaults.wheelUrl).toMatch(/\/wheels\/.+\.whl/);
    expect(defaults.wheelUrl).not.toMatch(/github\.com\/oliver\//);
  });

  it("createStudioAdapter pyodide defaults use local worker + local wheel URLs", () => {
    createStudioAdapter({
      kind: "pyodide",
      env: { MODE: "production", PROD: true },
    });
    expect(FakeWorker.instances.length).toBeGreaterThanOrEqual(1);
    const urlStr = decodeURIComponent(String(FakeWorker.instances[0]!.url));
    expect(urlStr).toMatch(/packaging\/pyodide\/worker\.js|\/worker\.js/);
    expect(urlStr).toMatch(/\/wheels\/.+\.whl|wheelUrl=/);
    expect(urlStr).not.toMatch(/github\.com\/oliver\//);
  });

  it("documents local defaults via .env.example or studioAdapter contract constants", () => {
    const envCandidates = [
      join(WEB_ROOT, ".env.example"),
      join(WEB_ROOT, ".env.development"),
      join(WEB_ROOT, ".env.local.example"),
    ];
    const envHit = envCandidates.find((p) => existsSync(p));
    const adapterSrc = readFileSync(STUDIO_ADAPTER_TS, "utf8");
    const hasCodeDefaults =
      /127\.0\.0\.1|localhost/.test(adapterSrc) &&
      /\/wheels\//.test(adapterSrc) &&
      !/DEFAULT_PYODIDE_WHEEL_URL\s*=\s*[\s\S]*?github\.com\/oliver\//.test(
        adapterSrc,
      );
    if (envHit) {
      const text = readFileSync(envHit, "utf8");
      expect(text).toMatch(/VITE_ENGINE_API_BASE_URL/);
      expect(text).toMatch(/localhost|127\.0\.0\.1/);
      expect(text).toMatch(/VITE_PYODIDE_WORKER_URL|VITE_PYODIDE_WHEEL_URL/);
      expect(text).not.toMatch(
        /VITE_PYODIDE_WHEEL_URL\s*=\s*https:\/\/github\.com\/oliver\//,
      );
    }
    expect(
      envHit || hasCodeDefaults,
      "need .env.example (or equiv) or code defaults with localhost API + local /wheels wheel",
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

  it("main.ts catches adapter init/step failures and surfaces them (non-silent)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/reportStudioAdapterError|studio-error|surfaceAdapter/);
    // bootstrap / Advance / Reset must not swallow rejections without catch.
    expect(src).toMatch(/catch\s*\(/);
    const bootstrap = src.match(/async function bootstrap[\s\S]*?\n\}/);
    expect(bootstrap, "expected bootstrap() in main.ts").toBeTruthy();
    expect(bootstrap![0]).toMatch(/catch|reportStudioAdapterError/);
    // Advance may use step_n (CAL-01 next-order-day) with a longer try body.
    expect(src).toMatch(
      /onAdvance[\s\S]{0,1200}catch|adapter\.step(?:_n)?[\s\S]{0,400}catch/,
    );
  });

  it("main.ts passes the original err into reportStudioAdapterError (banner + console)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    const calls = [...src.matchAll(/reportStudioAdapterError\(([^;]+)\)/g)];
    expect(calls.length).toBeGreaterThanOrEqual(4);
    for (const call of calls) {
      // Cause must be a separate argument (not only interpolated into the banner string).
      expect(call[1]).toMatch(/,\s*err\s*,?\s*$/);
    }
  });
});

describe("T-074 MockAdapter only when VITE_ENGINE_ADAPTER=mock", () => {
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
      { VITE_ENGINE_ADAPTER: "http", VITE_ENGINE_API_BASE_URL: "http://127.0.0.1:8000" },
      { VITE_ENGINE_ADAPTER: "pyodide" },
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

    const http = createStudioAdapter({
      kind: "http",
      baseUrl: "http://127.0.0.1:8000",
      fetch: vi.fn() as unknown as typeof fetch,
    });
    expect(http).not.toBeInstanceOf(MockAdapter);

    const pyodide = createStudioAdapter({
      kind: "pyodide",
      workerUrl: LOCAL_WORKER_PATH,
      wheelUrl: LOCAL_WHEEL_PATH,
    });
    expect(pyodide).not.toBeInstanceOf(MockAdapter);
  });

  it("default readiness path does not silently fall back to mock", () => {
    const kind = resolveStudioAdapterKind({
      MODE: "development",
      DEV: true,
    });
    expect(kind).not.toBe("mock");
    const adapter = createStudioAdapter({
      env: { MODE: "development", DEV: true },
      workerUrl: LOCAL_WORKER_PATH,
      wheelUrl: LOCAL_WHEEL_PATH,
    });
    expect(adapter).not.toBeInstanceOf(MockAdapter);
  });
});

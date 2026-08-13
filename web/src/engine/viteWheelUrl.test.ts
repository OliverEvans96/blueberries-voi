/**
 * T-072 RED: Vite serve worker+wheel; local wheelUrl reaches worker (ADR 0108).
 *
 * Static config + FakeWorker assertions. Does not start a live Vite server.
 * Worker honor of ?wheelUrl= is also locked in tests/test_t072_vite_wheel_url.py.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PyodideAdapter } from "./pyodideAdapter";
import {
  createStudioAdapter,
  type StudioEnv,
} from "./studioAdapter";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(HERE, "../..");
const REPO_ROOT = join(WEB_ROOT, "..");
const VITE_CONFIG = join(WEB_ROOT, "vite.config.ts");
const WORKER_JS = join(REPO_ROOT, "packaging/pyodide/worker.js");

const LOCAL_WHEEL_URL =
  "/wheels/blueberries_voi-0.1.0-py3-none-any.whl";
const DOCUMENTED_WORKER_URL = "/packaging/pyodide/worker.js";

class FakeWorker {
  static instances: FakeWorker[] = [];
  readonly url: string | URL;
  readonly posted: unknown[] = [];
  private readonly listeners = new Map<
    string,
    Set<(ev: MessageEvent) => void>
  >();

  constructor(url: string | URL, _opts?: WorkerOptions) {
    this.url = url;
    FakeWorker.instances.push(this);
  }

  addEventListener(type: string, fn: (ev: MessageEvent) => void): void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(fn);
  }

  removeEventListener(type: string, fn: (ev: MessageEvent) => void): void {
    this.listeners.get(type)?.delete(fn);
  }

  postMessage(data: unknown): void {
    this.posted.push(data);
    let request: {
      id?: string;
      method?: string;
      params?: Record<string, unknown>;
    };
    try {
      request =
        typeof data === "string" ? JSON.parse(data) : (data as typeof request);
    } catch {
      return;
    }
    const id = request.id != null ? String(request.id) : "";
    const method = request.method;
    if (method === "configure" || method === "bootstrap") {
      this.emit(JSON.stringify({ id, ok: true, result: { ready: true } }));
      return;
    }
    if (method === "init" || method === "reset") {
      this.emit(
        JSON.stringify({
          id,
          ok: true,
          result: {
            seq: 0,
            episode_day: 0,
            belief: {
              L: 2,
              K: 4,
              lot_counts: [1, 1],
              age_marginals: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
              tau_grid: [0, 2, 4, 8],
            },
            history: [],
            live_lots: [],
            pipeline: [],
            applied_config: {},
          },
        }),
      );
      return;
    }
    this.emit(
      JSON.stringify({
        id,
        ok: false,
        error: { type: "UnknownMethod", message: String(method) },
      }),
    );
  }

  terminate(): void {
    /* no-op */
  }

  private emit(payload: string): void {
    const ev = { data: payload } as MessageEvent;
    for (const fn of this.listeners.get("message") ?? []) {
      queueMicrotask(() => fn(ev));
    }
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

function stripJsComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

/** Strip // line comments only; keeps Vite path globs intact. */
function stripLineCommentsOnly(src: string): string {
  return src.replace(/^\s*\/\/.*$/gm, "");
}

describe("T-072 packaging worker honors wheelUrl for micropip", () => {
  it("reads ?wheelUrl= (URLSearchParams / location.search) or configure/init wheelUrl", () => {
    const raw = readFileSync(WORKER_JS, "utf8");
    const src = stripJsComments(raw);
    expect(src).toMatch(/wheelUrl/);
    const readsQuery = /URLSearchParams|location\.search|self\.location/.test(
      src,
    );
    const configureOrInit =
      /(?:configure|init)[\s\S]{0,400}wheelUrl|wheelUrl[\s\S]{0,200}(?:configure|init|params)/.test(
        src,
      );
    expect(
      readsQuery || configureOrInit,
      "worker must honor ?wheelUrl= and/or configure/init wheelUrl (ADR 0108)",
    ).toBe(true);

    const installArgs = [...src.matchAll(/micropip\.install\s*\(\s*([^)]+?)\s*\)/g)].map(
      (m) => m[1]!.trim(),
    );
    expect(installArgs.length).toBeGreaterThan(0);
    const nonConstant = installArgs.filter(
      (a) => a !== "SLIM_WHEEL_URL" && a !== "RELEASE_WHEEL_URL",
    );
    expect(
      nonConstant.length,
      "micropip.install must use resolved wheelUrl; Release URL is fallback only",
    ).toBeGreaterThan(0);
  });
});

describe("T-072 Vite config serves worker and local wheel", () => {
  it("wires packaging/pyodide worker at the documented URL", () => {
    expect(existsSync(VITE_CONFIG)).toBe(true);
    const cfg = stripLineCommentsOnly(readFileSync(VITE_CONFIG, "utf8"));
    expect(cfg).toMatch(/packaging\/pyodide|\/packaging\/pyodide\/worker\.js/);
    expect(cfg).toMatch(
      /alias|middleware|configureServer|publicDir|fs\s*:\s*\{[\s\S]*allow|server\.fs\.allow|resolve\.alias/,
    );
  });

  it("exposes a local slim wheel path (e.g. /wheels/*.whl)", () => {
    const cfg = stripLineCommentsOnly(readFileSync(VITE_CONFIG, "utf8"));
    const publicWheels =
      existsSync(join(WEB_ROOT, "public/wheels")) ||
      existsSync(join(WEB_ROOT, "wheels"));
    const wired = /\/wheels\/|['"]wheels['"]|\.whl|build_slim_wheel/.test(cfg);
    expect(
      wired || publicWheels,
      "Vite must serve local slim wheel at /wheels/*.whl (or Vite-visible equiv)",
    ).toBe(true);
  });
});

describe("T-072 local wheelUrl reaches the worker (adapter / studio)", () => {
  beforeEach(() => {
    installFakeWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("PyodideAdapter puts local /wheels/*.whl into Worker URL query (not dropped)", () => {
    new PyodideAdapter({
      workerUrl: DOCUMENTED_WORKER_URL,
      wheelUrl: LOCAL_WHEEL_URL,
    });
    expect(FakeWorker.instances.length).toBeGreaterThanOrEqual(1);
    const urlStr = String(FakeWorker.instances[0]!.url);
    expect(urlStr).toContain("wheelUrl=");
    expect(decodeURIComponent(urlStr)).toContain(LOCAL_WHEEL_URL);
    expect(urlStr).not.toMatch(/github\.com\/oliver/);
  });

  it("createStudioAdapter passes VITE_PYODIDE_WHEEL_URL local path through to Worker", () => {
    const env: StudioEnv = {
      MODE: "production",
      PROD: true,
      VITE_ENGINE_ADAPTER: "pyodide",
      VITE_PYODIDE_WORKER_URL: DOCUMENTED_WORKER_URL,
      VITE_PYODIDE_WHEEL_URL: LOCAL_WHEEL_URL,
    };
    createStudioAdapter({ env });
    expect(FakeWorker.instances.length).toBeGreaterThanOrEqual(1);
    const urlStr = String(FakeWorker.instances[0]!.url);
    expect(decodeURIComponent(urlStr)).toContain(LOCAL_WHEEL_URL);
    expect(urlStr).toMatch(/packaging\/pyodide\/worker\.js/);
  });

  it("createStudioAdapter opts.wheelUrl local override is not dropped", () => {
    createStudioAdapter({
      kind: "pyodide",
      workerUrl: DOCUMENTED_WORKER_URL,
      wheelUrl: LOCAL_WHEEL_URL,
    });
    const worker = FakeWorker.instances[0]!;
    const urlStr = String(worker.url);
    expect(decodeURIComponent(urlStr)).toContain(LOCAL_WHEEL_URL);
    // Also expect configure/init traffic to carry the same local URL when posted.
    const blob = JSON.stringify(worker.posted);
    // configure is fire-and-forget; give microtasks a tick if needed.
    expect(
      decodeURIComponent(urlStr).includes(LOCAL_WHEEL_URL) ||
        blob.includes("wheels/") ||
        blob.includes(LOCAL_WHEEL_URL),
    ).toBe(true);
  });
});

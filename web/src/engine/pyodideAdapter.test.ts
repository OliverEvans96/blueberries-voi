/**
 * T-055 RED: PyodideAdapter implements EngineAdapter, talks worker RPC
 * (JSON Snapshot / DayDelta), Release/slim wheel + DEMO_BUDGETS defaults.
 * Does not cover HttpAdapter (T-056).
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EngineAdapter } from "./adapter";
import {
  DEFAULT_DEMO_BUDGETS,
  PyodideAdapter,
  type DemoBudgets,
  type PyodideAdapterOpts,
} from "./pyodideAdapter";
import { FORBIDDEN_ENGINE_KEYS, type DayDelta, type Snapshot } from "./types";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(HERE, "../../..");
const WORKER_PATH = join(REPO_ROOT, "packaging/pyodide/worker.js");

const SAMPLE_BELIEF = {
  L: 2,
  K: 4,
  lot_counts: [3.6, 3.32],
  age_marginals: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
  tau_grid: [0, 2.6666666666666665, 5.333333333333333, 8],
};

const SAMPLE_SNAPSHOT: Snapshot = {
  seq: 0,
  episode_day: 0,
  belief: { ...SAMPLE_BELIEF, age_marginals: [...SAMPLE_BELIEF.age_marginals] },
  history: [],
  live_lots: [],
  pipeline: [],
  applied_config: { ...DEFAULT_DEMO_BUDGETS, L: 2, K: 4, seed: 42 },
};

const SAMPLE_DELTA: DayDelta = {
  seq: 1,
  episode_day: 0,
  day: {
    day: 0,
    lots: [],
    sales_total: 0,
    waste_total: 0,
    demand: 31,
    order_qty: 16,
    arrivals: 0,
    stockout: 0,
    age_at_receipt: 0,
  },
  drop_oldest: false,
  belief: {
    ...SAMPLE_BELIEF,
    lot_counts: [1.1, 1.25],
    age_marginals: [
      0.266, 0.255, 0.244, 0.235, 0.266, 0.255, 0.244, 0.235,
    ],
  },
  live_lots: [],
  pipeline: [{ qty: 16, arrival_day: 1 }],
};

const RELEASE_WHEEL =
  "https://github.com/oliver/blueberries-voi/releases/download/v0.1.0/" +
  "blueberries_voi-0.1.0-py3-none-any.whl";
const WORKER_URL = "/packaging/pyodide/worker.js";

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

/** Node FakeWorker: JSON-string RPC like packaging/pyodide/worker.js. */
class FakeWorker {
  static instances: FakeWorker[] = [];
  readonly url: string | URL;
  readonly posted: unknown[] = [];
  private readonly listeners = new Map<string, Set<(ev: MessageEvent) => void>>();

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
    let request: { id?: string; method?: string; params?: Record<string, unknown> };
    try {
      request = typeof data === "string" ? JSON.parse(data) : (data as typeof request);
    } catch {
      this.emit(
        JSON.stringify({
          id: "",
          ok: false,
          error: { type: "JSONDecodeError", message: "bad request" },
        }),
      );
      return;
    }
    const id = request.id != null ? String(request.id) : "";
    const method = request.method;
    let result: unknown;
    if (method === "init" || method === "reset") {
      result = SAMPLE_SNAPSHOT;
    } else if (method === "step" || method === "act") {
      result = SAMPLE_DELTA;
    } else if (method === "step_n") {
      const orders = (request.params?.orders as number[] | undefined) ?? [];
      result = orders.map((_, i) => ({
        ...SAMPLE_DELTA,
        seq: i + 1,
        day: { ...SAMPLE_DELTA.day, day: i, order_qty: orders[i] ?? 0 },
      }));
    } else if (method === "bootstrap" || method === "configure") {
      result = { ready: true };
    } else {
      this.emit(
        JSON.stringify({
          id,
          ok: false,
          error: { type: "UnknownMethod", message: `unknown method ${method}` },
        }),
      );
      return;
    }
    this.emit(JSON.stringify({ id, ok: true, result }));
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

function lastParsedRequest(worker: FakeWorker): {
  id: string;
  method: string;
  params: Record<string, unknown>;
} {
  expect(worker.posted.length).toBeGreaterThan(0);
  const raw = worker.posted[worker.posted.length - 1];
  expect(typeof raw === "string" || (raw !== null && typeof raw === "object")).toBe(
    true,
  );
  const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
  expect(parsed).toEqual(
    expect.objectContaining({
      id: expect.anything(),
      method: expect.any(String),
    }),
  );
  return parsed as {
    id: string;
    method: string;
    params: Record<string, unknown>;
  };
}

function defaultOpts(overrides: Partial<PyodideAdapterOpts> = {}): PyodideAdapterOpts {
  return {
    workerUrl: WORKER_URL,
    wheelUrl: RELEASE_WHEEL,
    ...overrides,
  };
}

describe("PyodideAdapter implements EngineAdapter", () => {
  beforeEach(() => {
    installFakeWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("constructs with workerUrl, wheelUrl, and optional budgets", () => {
    const budgets: DemoBudgets = { ...DEFAULT_DEMO_BUDGETS, n_particles: 100 };
    const adapter = new PyodideAdapter(defaultOpts({ budgets })) as EngineAdapter;
    expect(adapter).toBeInstanceOf(PyodideAdapter);
    expect(typeof adapter.init).toBe("function");
    expect(typeof adapter.step).toBe("function");
    expect(typeof adapter.step_n).toBe("function");
    expect(typeof adapter.reset).toBe("function");
    expect(typeof adapter.act).toBe("function");
  });

  it("spawns a Worker from workerUrl and communicates the Release wheelUrl", () => {
    new PyodideAdapter(defaultOpts());
    expect(
      FakeWorker.instances.length,
      "PyodideAdapter must construct a Worker(workerUrl)",
    ).toBeGreaterThanOrEqual(1);
    const worker = FakeWorker.instances[0]!;
    const urlStr = String(worker.url);
    expect(urlStr).toContain("worker");
    // wheelUrl must reach the worker (bootstrap/configure/init params or URL query).
    const postedBlob = JSON.stringify(worker.posted);
    const urlBlob = urlStr + postedBlob;
    expect(urlBlob).toContain("blueberries_voi");
    expect(urlBlob).toMatch(/\.whl|wheelUrl|wheel_url|micropip/i);
  });

  it("forwards init / step / step_n / reset / act as worker RPC and returns Snapshot/DayDelta", async () => {
    const adapter = new PyodideAdapter(defaultOpts()) as EngineAdapter;
    expect(
      FakeWorker.instances.length,
      "PyodideAdapter must construct a Worker(workerUrl)",
    ).toBeGreaterThanOrEqual(1);
    const worker = FakeWorker.instances[0]!;

    const snap = await adapter.init({ seed: 42 });
    expect(snap).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        episode_day: expect.any(Number),
        belief: expect.objectContaining({
          L: expect.any(Number),
          K: expect.any(Number),
          lot_counts: expect.any(Array),
          age_marginals: expect.any(Array),
          tau_grid: expect.any(Array),
        }),
      }),
    );
    let req = lastParsedRequest(worker);
    expect(req.method).toBe("init");

    const delta = await adapter.step(16);
    expect(delta).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        episode_day: expect.any(Number),
        day: expect.any(Object),
        drop_oldest: expect.any(Boolean),
      }),
    );
    req = lastParsedRequest(worker);
    expect(req.method).toBe("step");
    expect(req.params).toEqual(expect.objectContaining({ order_qty: 16 }));

    const batch = await adapter.step_n([8, 8]);
    expect(Array.isArray(batch)).toBe(true);
    expect(batch).toHaveLength(2);
    for (const d of batch) {
      expect(d).toEqual(
        expect.objectContaining({
          day: expect.any(Object),
          drop_oldest: expect.any(Boolean),
        }),
      );
    }
    req = lastParsedRequest(worker);
    expect(req.method).toBe("step_n");
    expect(req.params).toEqual(expect.objectContaining({ orders: [8, 8] }));

    const resetSnap = await adapter.reset({ seed: 7 });
    expect(resetSnap).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        belief: expect.objectContaining({ age_marginals: expect.any(Array) }),
      }),
    );
    req = lastParsedRequest(worker);
    expect(req.method).toBe("reset");

    expect(typeof adapter.act).toBe("function");
    const acted = await adapter.act!({ policy: null });
    expect(acted).toEqual(
      expect.objectContaining({
        day: expect.any(Object),
        drop_oldest: expect.any(Boolean),
      }),
    );
    req = lastParsedRequest(worker);
    expect(req.method).toBe("act");
  });
});

describe("PyodideAdapter main-thread plain data (no PyProxy)", () => {
  beforeEach(() => {
    installFakeWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("source never calls runPython / loadPyodide on the main thread", () => {
    const src = readFileSync(join(HERE, "pyodideAdapter.ts"), "utf8");
    // Strip block + line comments so RED stubs cannot pass via documentation alone.
    const code = src
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toMatch(/\brunPython(?:Async)?\b/);
    expect(code).not.toMatch(/\bloadPyodide\b/);
    expect(code).not.toMatch(/\bpyimport\b/);
    expect(code).toMatch(/\bnew\s+Worker\b/);
    expect(code).toMatch(/\.postMessage\s*\(/);
    expect(code).toMatch(/JSON\.(?:parse|stringify)\s*\(/);
  });

  it("returns structured-clone / JSON-safe plain objects from RPC results", async () => {
    const adapter = new PyodideAdapter(defaultOpts()) as EngineAdapter;
    expect(
      FakeWorker.instances.length,
      "PyodideAdapter must construct a Worker(workerUrl)",
    ).toBeGreaterThanOrEqual(1);

    const snap = await adapter.init({ seed: 42 });
    expect(snap).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        belief: expect.objectContaining({ age_marginals: expect.any(Array) }),
      }),
    );
    expect(JSON.parse(JSON.stringify(snap))).toEqual(snap);
    expect(snap).not.toHaveProperty("$$");
    expect(snap).not.toHaveProperty("destroy");
    expect(snap).not.toHaveProperty("toJs");

    const delta = await adapter.step(8);
    expect(delta).toEqual(
      expect.objectContaining({
        day: expect.any(Object),
        drop_oldest: expect.any(Boolean),
      }),
    );
    expect(JSON.parse(JSON.stringify(delta))).toEqual(delta);
    expect(delta).not.toHaveProperty("$$");
    expect(delta).not.toHaveProperty("toJs");

    // Worker traffic itself must be string or cloneable plain object — never a PyProxy.
    const worker = FakeWorker.instances[0]!;
    expect(worker.posted.length).toBeGreaterThan(0);
    for (const msg of worker.posted) {
      if (typeof msg === "string") {
        expect(() => JSON.parse(msg)).not.toThrow();
      } else {
        expect(JSON.parse(JSON.stringify(msg))).toEqual(msg);
      }
    }
  });

  it("Snapshot / DayDelta omit presentation keys for the projector", async () => {
    const adapter = new PyodideAdapter(defaultOpts()) as EngineAdapter;
    const snap = await adapter.init({});
    expect(snap).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        belief: expect.objectContaining({
          L: expect.any(Number),
          K: expect.any(Number),
          age_marginals: expect.any(Array),
        }),
      }),
    );
    for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
      expect(collectKeys(snap).has(forbidden)).toBe(false);
    }
    const delta = await adapter.step(8);
    expect(delta).toEqual(
      expect.objectContaining({
        day: expect.any(Object),
        drop_oldest: expect.any(Boolean),
      }),
    );
    for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
      expect(collectKeys(delta).has(forbidden)).toBe(false);
    }
    if (delta.belief) {
      expect(delta.belief).not.toHaveProperty("density");
    }
  });
});

describe("PyodideAdapter demo budget defaults", () => {
  beforeEach(() => {
    installFakeWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("DEFAULT_DEMO_BUDGETS matches ADR 0099 dialed caps", () => {
    expect(DEFAULT_DEMO_BUDGETS.n_particles).toBeLessThanOrEqual(200);
    expect(DEFAULT_DEMO_BUDGETS.H).toBeLessThanOrEqual(7);
    expect(DEFAULT_DEMO_BUDGETS.n_rollout_paths).toBeLessThanOrEqual(2);
    expect(DEFAULT_DEMO_BUDGETS.candidate_case_radius).toBeLessThanOrEqual(1);
  });

  it("init uses DEMO_BUDGETS by default when budgets opts are omitted", async () => {
    const adapter = new PyodideAdapter(defaultOpts()) as EngineAdapter;
    expect(
      FakeWorker.instances.length,
      "PyodideAdapter must construct a Worker(workerUrl)",
    ).toBeGreaterThanOrEqual(1);
    await adapter.init({});
    const worker = FakeWorker.instances[0]!;
    const initMsgs = worker.posted
      .map((raw) => (typeof raw === "string" ? JSON.parse(raw) : raw))
      .filter((m: { method?: string }) => m.method === "init");
    expect(initMsgs.length).toBeGreaterThanOrEqual(1);
    const params = initMsgs[0]!.params as {
      config?: Record<string, number>;
    };
    const config = params.config ?? {};
    expect(Number(config.n_particles)).toBeLessThanOrEqual(200);
    expect(Number(config.H)).toBeLessThanOrEqual(7);
    expect(Number(config.n_rollout_paths)).toBeLessThanOrEqual(2);
    expect(Number(config.candidate_case_radius)).toBeLessThanOrEqual(1);
    // Must actually ship the dialed preset (not omit budgets entirely).
    expect(config).toEqual(
      expect.objectContaining({
        n_particles: expect.any(Number),
        H: expect.any(Number),
      }),
    );
  });
});

describe("PyodideAdapter integration smoke (Release wheel / Pyodide 314)", () => {
  it("packaging worker pins Pyodide 314.0.4 and Release/slim wheel install", () => {
    const workerSrc = readFileSync(WORKER_PATH, "utf8");
    expect(workerSrc).toMatch(/314\.0\.4/);
    expect(workerSrc).toMatch(/micropip|\.whl/);
    expect(workerSrc).toMatch(/\binit\b/);
    expect(workerSrc).toMatch(/\bstep\b/);
  });

  it("ships a clear pass/fail smoke that drives PyodideAdapter init+step", () => {
    // Prefer a web-side smoke that imports PyodideAdapter; packaging smoke alone
    // is T-047 (session_rpc). T-055 must wire the D3 adapter module.
    const candidates = [
      join(HERE, "pyodideAdapter.smoke.ts"),
      join(HERE, "pyodideAdapterSmoke.ts"),
      join(REPO_ROOT, "web/scripts/smoke-pyodide-adapter.mjs"),
      join(REPO_ROOT, "web/scripts/smoke-pyodide-adapter.ts"),
      join(REPO_ROOT, "packaging/pyodide/smoke_adapter.js"),
      join(REPO_ROOT, "packaging/pyodide/smoke_adapter.mjs"),
    ];
    const adapterSrc = readFileSync(join(HERE, "pyodideAdapter.ts"), "utf8");
    const foundFile = candidates.find((p) => {
      try {
        readFileSync(p);
        return true;
      } catch {
        return false;
      }
    });
    const exportsSmoke =
      /\brunPyodideAdapterSmoke\b|\bsmokeInitStep\b|\bintegrationSmoke\b/.test(
        adapterSrc,
      );
    expect(
      foundFile != null || exportsSmoke,
      "expected a PyodideAdapter init+step smoke script/export with clear pass/fail",
    ).toBe(true);

    if (foundFile) {
      const smokeSrc = readFileSync(foundFile, "utf8");
      expect(smokeSrc).toMatch(/PyodideAdapter/);
      expect(smokeSrc).toMatch(/\binit\b/);
      expect(smokeSrc).toMatch(/\bstep\b/);
      expect(smokeSrc).toMatch(/314\.0\.4|\.whl|wheelUrl|wheel_url/);
    }
  });
});

/**
 * T-098 RED: typed ActOpts, HTTP nest / Pyodide flatten, MockAdapter.act.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockAdapter } from "../mock/adapter";
import type { EngineAdapter } from "./adapter";
import {
  DEFAULT_DEMO_BUDGETS,
  PyodideAdapter,
  type PyodideAdapterOpts,
} from "./pyodideAdapter";
import {
  FORBIDDEN_ENGINE_KEYS,
  type ActOpts,
  type DayDelta,
  type Snapshot,
} from "./types";

const HERE = dirname(fileURLToPath(import.meta.url));
const TYPES_SRC = join(HERE, "types.ts");
const MOCK_ADAPTER_SRC = join(HERE, "../mock/adapter.ts");
const PYODIDE_ADAPTER_SRC = join(HERE, "pyodideAdapter.ts");

const BASE = "http://127.0.0.1:8000";
const SESSION_ID = "sess-actopts-001";

const SNAPSHOT: Snapshot = {
  seq: 0,
  episode_day: 0,
  belief: {
    L: 1,
    K: 2,
    lot_counts: [4],
    age_marginals: [0.5, 0.5],
    tau_grid: [0, 4],
  },
  history: [],
  live_lots: [],
  pipeline: [],
};

const DAY_DELTA: DayDelta = {
  seq: 1,
  episode_day: 1,
  day: {
    day: 0,
    demand: 10,
    order_qty: 8,
    sales_total: 0,
    waste_total: 0,
    arrivals: 0,
    L: 0,
  },
  drop_oldest: false,
  belief: SNAPSHOT.belief,
  live_lots: [],
  pipeline: [],
};

const BUDGET_KEYS = [
  "alpha",
  "rho",
  "H",
  "n_rollout_paths",
  "candidate_case_radius",
  "n_particles",
  "order_qty",
  "q",
] as const;

/** Mixed nested + flat caller shape both adapters must accept. */
const CALLER_OPTS: ActOpts = {
  policy: "damped_sw",
  alpha: 0.9,
  budgets: {
    rho: 0.8,
    H: 7,
    n_rollout_paths: 2,
    candidate_case_radius: 1,
    n_particles: 200,
  },
};

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

type FetchCall = {
  url: string;
  method: string;
  body: unknown;
};

function installMockFetch(
  handler: (call: FetchCall) => { status: number; json?: unknown; text?: string },
): { calls: FetchCall[]; fetch: typeof fetch } {
  const calls: FetchCall[] = [];
  const fetchImpl: typeof fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    let body: unknown = undefined;
    if (typeof init?.body === "string" && init.body.length > 0) {
      body = JSON.parse(init.body) as unknown;
    }
    const call: FetchCall = { url, method, body };
    calls.push(call);
    const res = handler(call);
    return {
      ok: res.status >= 200 && res.status < 300,
      status: res.status,
      json: async () => res.json,
      text: async () => res.text ?? JSON.stringify(res.json ?? null),
      headers: new Headers({ "content-type": "application/json" }),
    } as Response;
  }) as typeof fetch;
  return { calls, fetch: fetchImpl };
}

function defaultRouteHandler(call: FetchCall): { status: number; json?: unknown } {
  const path = new URL(call.url).pathname;
  if (call.method === "POST" && path === "/sessions") {
    return { status: 200, json: { session_id: SESSION_ID } };
  }
  if (call.method === "POST" && path === `/sessions/${SESSION_ID}/act`) {
    return { status: 200, json: DAY_DELTA };
  }
  if (call.method === "POST" && path === `/sessions/${SESSION_ID}/init`) {
    return { status: 200, json: SNAPSHOT };
  }
  return { status: 404, json: { ok: false } };
}

/** Node FakeWorker: JSON-string RPC (same pattern as pyodideAdapter.test.ts). */
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
    this.emit(JSON.stringify({ id, ok: true, result: DAY_DELTA }));
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

function lastActParams(worker: FakeWorker): Record<string, unknown> {
  const actMsgs = worker.posted
    .map((raw) => (typeof raw === "string" ? JSON.parse(raw) : raw))
    .filter((m: { method?: string }) => m.method === "act");
  expect(actMsgs.length).toBeGreaterThanOrEqual(1);
  return (actMsgs[actMsgs.length - 1]!.params ?? {}) as Record<string, unknown>;
}

function pyodideOpts(overrides: Partial<PyodideAdapterOpts> = {}): PyodideAdapterOpts {
  return {
    workerUrl: "/packaging/pyodide/worker.js",
    wheelUrl:
      "https://github.com/oliver/blueberries-voi/releases/download/v0.1.0/" +
      "blueberries_voi-0.1.0-py3-none-any.whl",
    budgets: { ...DEFAULT_DEMO_BUDGETS },
    ...overrides,
  };
}

describe("Typed ActOpts (T-098 / ADR 0117)", () => {
  it("exports ActPolicyName, ActBudgets, and typed ActOpts (not only Record)", () => {
    const src = readFileSync(TYPES_SRC, "utf8");
    expect(src).toMatch(/export\s+type\s+ActPolicyName\b/);
    expect(src).toMatch(/export\s+type\s+ActBudgets\b/);
    expect(src).toMatch(/export\s+type\s+ActOpts\b/);
    // Must not remain the untyped Record alias alone.
    expect(src).not.toMatch(
      /export\s+type\s+ActOpts\s*=\s*Record\s*<\s*string\s*,\s*unknown\s*>\s*;/,
    );
    for (const key of BUDGET_KEYS) {
      expect(src).toMatch(new RegExp(`\\b${key}\\b`));
    }
    for (const policy of [
      "damped_sw",
      "sw",
      "rollout",
      "ctl",
      "rollout_order",
      "constant",
      "const",
      "fixed",
    ]) {
      expect(src).toContain(`"${policy}"`);
    }
  });

  it("caller-facing ActOpts compiles at use sites (policy + nested/flat budgets)", () => {
    const nested: ActOpts = {
      policy: "rollout",
      budgets: { alpha: 0.9, rho: 0.8, H: 7 },
    };
    const flat: ActOpts = {
      policy: "constant",
      order_qty: 16,
      q: 16,
    };
    expect(nested.policy).toBe("rollout");
    expect(flat.order_qty ?? flat.q).toBe(16);
  });
});

describe("PyodideAdapter.act uses flat worker params (T-098)", () => {
  beforeEach(() => {
    installFakeWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("flattens policy + budget knobs (no nested budgets object on the wire)", async () => {
    const adapter = new PyodideAdapter(pyodideOpts()) as EngineAdapter;
    expect(typeof adapter.act).toBe("function");
    await adapter.act!(CALLER_OPTS);

    const worker = FakeWorker.instances[0]!;
    const params = lastActParams(worker);
    expect(params).not.toHaveProperty("budgets");
    expect(params.policy).toBe("damped_sw");
    expect(params.alpha).toBe(0.9);
    expect(params.rho).toBe(0.8);
    expect(params.H).toBe(7);
    expect(params.n_rollout_paths).toBe(2);
    expect(params.candidate_case_radius).toBe(1);
    expect(params.n_particles).toBe(200);
  });
});

describe("MockAdapter.act returns DayDelta (T-098)", () => {
  it("exists, advances one mock day, and chooses order from opts", async () => {
    const adapter = new MockAdapter(42);
    await adapter.init({});
    const before = await adapter.reset({});
    const seqBefore = before.seq;
    const dayBefore = before.episode_day;

    expect(typeof adapter.act).toBe("function");
    const delta = await adapter.act!({
      policy: "constant",
      order_qty: 16,
    });

    expect(delta).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        episode_day: expect.any(Number),
        day: expect.any(Object),
        drop_oldest: expect.any(Boolean),
      }),
    );
    expect(delta.seq).toBe(seqBefore + 1);
    // Snapshot.episode_day is the next day to act (EngineSession parity after
    // CAL-01); DayDelta.episode_day is the day just completed — equal here.
    expect(delta.episode_day).toBe(dayBefore);
    const day = delta.day as { order_qty?: number };
    expect(day.order_qty).toBe(16);
  });

  it("act DayDelta omits forbidden presentation keys", async () => {
    const adapter = new MockAdapter(42);
    await adapter.init({});
    expect(typeof adapter.act).toBe("function");
    const delta = await adapter.act!({ policy: "damped_sw", alpha: 0.9 });
    const keys = collectKeys(delta);
    for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
      expect(keys.has(forbidden)).toBe(false);
    }
    expect(delta).not.toHaveProperty("pnl_series");
    expect(delta).not.toHaveProperty("economics");
  });

  it("documents that mock act is not numeric-parity with Python rollout / damped SW", () => {
    const src = readFileSync(MOCK_ADAPTER_SRC, "utf8");
    expect(src).toMatch(/\bact\s*\(/);
    // Comment / docstring near act must disclaim Python numeric parity.
    expect(src).toMatch(/not.*numeric|≠|!=.*parity|not.*parity/i);
    expect(src).toMatch(/rollout_order|DampedSurvivalWeightedPolicy|Python/i);
  });
});

describe("Shared normalize surface (T-098)", () => {
  it("adapters (or a shared helper) encode nest vs flat from one caller shape", () => {
    const pySrc = readFileSync(PYODIDE_ADAPTER_SRC, "utf8");
    const pyFlattens = /act\s*\(/.test(pySrc);
    expect(pyFlattens).toBe(true);
    // Current Pyodide spreads raw opts — must stop treating nested budgets as wire shape.
    // After implement, act must not simply `{ ...(opts ?? {}) }` without flattening.
    const pyActBody = pySrc.match(/async\s+act\s*\([^)]*\)[^{]*\{[\s\S]*?\n  \}/);
    expect(pyActBody?.[0] ?? pySrc).not.toMatch(
      /return\s+\(await\s+this\.call\(\s*"act"\s*,\s*\{\s*\.\.\.\(opts\s*\?\?\s*\{\}\)\s*\}\s*\)/,
    );
  });
});

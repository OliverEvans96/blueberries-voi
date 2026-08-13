/**
 * T-056 RED: HttpAdapter implements EngineAdapter via T-049 ASGI session routes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EngineAdapter } from "./adapter";
import { HttpAdapter } from "./httpAdapter";
import { ViewModelProjector } from "./projector";
import { FORBIDDEN_ENGINE_KEYS, type DayDelta, type Snapshot } from "./types";

const BASE = "http://127.0.0.1:8000";
const SESSION_ID = "sess-test-001";

const SNAPSHOT: Snapshot = {
  seq: 0,
  episode_day: 0,
  belief: {
    L: 2,
    K: 4,
    lot_counts: [3, 3],
    age_marginals: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
    tau_grid: [0, 2.67, 5.33, 8],
  },
  history: [],
  live_lots: [],
  pipeline: [],
  applied_config: { seed: 42 },
};

const DAY_DELTA: DayDelta = {
  seq: 1,
  episode_day: 0,
  day: {
    day: 0,
    demand: 31,
    order_qty: 16,
    sales_total: 0,
    waste_total: 0,
    arrivals: 0,
    L: 0,
  },
  drop_oldest: false,
  belief: SNAPSHOT.belief,
  live_lots: [],
  pipeline: [{ qty: 16, arrival_day: 1 }],
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

function defaultRouteHandler(call: FetchCall): {
  status: number;
  json?: unknown;
} {
  const path = new URL(call.url).pathname;
  if (call.method === "POST" && path === "/sessions") {
    return { status: 200, json: { session_id: SESSION_ID } };
  }
  if (call.method === "POST" && path === `/sessions/${SESSION_ID}/init`) {
    return { status: 200, json: SNAPSHOT };
  }
  if (call.method === "POST" && path === `/sessions/${SESSION_ID}/step`) {
    return { status: 200, json: DAY_DELTA };
  }
  if (call.method === "POST" && path === `/sessions/${SESSION_ID}/step_n`) {
    return { status: 200, json: { deltas: [DAY_DELTA, { ...DAY_DELTA, seq: 2 }] } };
  }
  if (call.method === "POST" && path === `/sessions/${SESSION_ID}/reset`) {
    return { status: 200, json: { ...SNAPSHOT, seq: 0 } };
  }
  if (call.method === "POST" && path === `/sessions/${SESSION_ID}/act`) {
    return { status: 200, json: DAY_DELTA };
  }
  if (call.method === "DELETE" && path === `/sessions/${SESSION_ID}`) {
    return { status: 204 };
  }
  return { status: 404, json: { ok: false, error: { type: "not_found", message: path } } };
}

describe("HttpAdapter implements EngineAdapter (T-049 routes)", () => {
  it("exposes init / step / step_n / reset as EngineAdapter", () => {
    const { fetch } = installMockFetch(defaultRouteHandler);
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch }) as unknown as EngineAdapter;
    expect(typeof adapter.init).toBe("function");
    expect(typeof adapter.step).toBe("function");
    expect(typeof adapter.step_n).toBe("function");
    expect(typeof adapter.reset).toBe("function");
  });

  it("init returns a Snapshot (seq, episode_day, flat belief)", async () => {
    const { fetch } = installMockFetch(defaultRouteHandler);
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
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
    const { L, K, age_marginals } = snap.belief;
    expect(age_marginals).toHaveLength(L * K);
  });

  it("step returns a DayDelta (day + drop_oldest)", async () => {
    const { fetch } = installMockFetch(defaultRouteHandler);
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42 });
    const delta = await adapter.step(16);
    expect(delta).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        episode_day: expect.any(Number),
        day: expect.any(Object),
        drop_oldest: expect.any(Boolean),
      }),
    );
  });

  it("step_n returns DayDelta[] (unwraps { deltas })", async () => {
    const { fetch } = installMockFetch(defaultRouteHandler);
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42 });
    const deltas = await adapter.step_n([16, 8]);
    expect(Array.isArray(deltas)).toBe(true);
    expect(deltas.length).toBeGreaterThanOrEqual(1);
    expect(deltas[0]).toEqual(
      expect.objectContaining({ day: expect.any(Object), drop_oldest: expect.any(Boolean) }),
    );
  });

  it("reset returns a Snapshot", async () => {
    const { fetch } = installMockFetch(defaultRouteHandler);
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42 });
    const snap = await adapter.reset({ seed: 42 });
    expect(snap).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        belief: expect.objectContaining({ age_marginals: expect.any(Array) }),
      }),
    );
  });
});

describe("HttpAdapter fetch contract (paths + JSON bodies)", () => {
  let calls: FetchCall[];
  let fetch: typeof globalThis.fetch;

  beforeEach(() => {
    ({ calls, fetch } = installMockFetch(defaultRouteHandler));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a session with POST /sessions (construct or init)", async () => {
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42 });
    const create = calls.find(
      (c) => c.method === "POST" && new URL(c.url).pathname === "/sessions",
    );
    expect(create).toBeDefined();
    expect(create!.url.startsWith(BASE)).toBe(true);
  });

  it("init POSTs /sessions/{id}/init with JSON { config, seed? }", async () => {
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42, H: 7 });
    const initCall = calls.find(
      (c) =>
        c.method === "POST" &&
        new URL(c.url).pathname === `/sessions/${SESSION_ID}/init`,
    );
    expect(initCall).toBeDefined();
    expect(initCall!.body).toEqual(
      expect.objectContaining({
        config: expect.any(Object),
      }),
    );
    const headersProbe = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
      (args) => String(args[0]).includes("/init"),
    );
    expect(headersProbe).toBeDefined();
    const initOpts = headersProbe![1] as RequestInit;
    const rawHeaders = initOpts.headers;
    const contentType =
      rawHeaders instanceof Headers
        ? rawHeaders.get("content-type")
        : Array.isArray(rawHeaders)
          ? rawHeaders.find(([k]) => k.toLowerCase() === "content-type")?.[1]
          : (rawHeaders as Record<string, string> | undefined)?.["Content-Type"]
            ?? (rawHeaders as Record<string, string> | undefined)?.["content-type"];
    expect(String(contentType)).toMatch(/application\/json/i);
  });

  it("step POSTs /sessions/{id}/step with { order_qty }", async () => {
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42 });
    await adapter.step(16);
    const stepCall = calls.find(
      (c) =>
        c.method === "POST" &&
        new URL(c.url).pathname === `/sessions/${SESSION_ID}/step`,
    );
    expect(stepCall).toBeDefined();
    expect(stepCall!.body).toEqual({ order_qty: 16 });
  });

  it("step_n POSTs /sessions/{id}/step_n with { orders }", async () => {
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42 });
    await adapter.step_n([16, 8]);
    const stepN = calls.find(
      (c) =>
        c.method === "POST" &&
        new URL(c.url).pathname === `/sessions/${SESSION_ID}/step_n`,
    );
    expect(stepN).toBeDefined();
    expect(stepN!.body).toEqual({ orders: [16, 8] });
  });

  it("reset POSTs /sessions/{id}/reset (keeps session)", async () => {
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42 });
    await adapter.reset({ seed: 7 });
    const resetCall = calls.find(
      (c) =>
        c.method === "POST" &&
        new URL(c.url).pathname === `/sessions/${SESSION_ID}/reset`,
    );
    expect(resetCall).toBeDefined();
    // No second POST /sessions after reset — same session_id.
    const creates = calls.filter(
      (c) => c.method === "POST" && new URL(c.url).pathname === "/sessions",
    );
    expect(creates).toHaveLength(1);
  });

  it("dispose DELETEs /sessions/{id}", async () => {
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42 });
    await adapter.dispose();
    const del = calls.find(
      (c) =>
        c.method === "DELETE" &&
        new URL(c.url).pathname === `/sessions/${SESSION_ID}`,
    );
    expect(del).toBeDefined();
  });
});

describe("HttpAdapter Snapshot/DayDelta only (no presentation keys)", () => {
  it("init and step payloads omit economics / pnl / ghost / heatmap", async () => {
    const { fetch } = installMockFetch(defaultRouteHandler);
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    const snap = await adapter.init({ seed: 42 });
    const delta = await adapter.step(16);
    // Must be real wire payloads (not empty stubs) and must omit presentation keys.
    expect(snap).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        belief: expect.objectContaining({ age_marginals: expect.any(Array) }),
      }),
    );
    expect(delta).toEqual(
      expect.objectContaining({
        day: expect.any(Object),
        drop_oldest: expect.any(Boolean),
      }),
    );
    for (const payload of [snap, delta]) {
      const keys = collectKeys(payload);
      for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
        expect(keys.has(forbidden)).toBe(false);
      }
    }
  });
});

describe("HttpAdapter base URL (constructor / env)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("uses constructor baseUrl as the request origin", async () => {
    const { calls, fetch } = installMockFetch(defaultRouteHandler);
    const custom = "http://localhost:9999";
    const adapter = new HttpAdapter({ baseUrl: custom, fetch });
    await adapter.init({ seed: 1 });
    expect(calls.length).toBeGreaterThan(0);
    for (const c of calls) {
      expect(c.url.startsWith(custom)).toBe(true);
    }
  });

  it("reads VITE_ENGINE_API_BASE_URL when baseUrl omitted", async () => {
    vi.stubEnv("VITE_ENGINE_API_BASE_URL", "http://127.0.0.1:8765");
    const { calls, fetch } = installMockFetch(defaultRouteHandler);
    const adapter = new HttpAdapter({ fetch });
    await adapter.init({ seed: 1 });
    expect(calls.length).toBeGreaterThan(0);
    for (const c of calls) {
      expect(c.url.startsWith("http://127.0.0.1:8765")).toBe(true);
    }
  });
});

describe("Economics stay in projector (no HttpAdapter POST)", () => {
  it("ViewModelProjector.setEconomics does not trigger HttpAdapter fetch", async () => {
    const { calls, fetch } = installMockFetch(defaultRouteHandler);
    const adapter = new HttpAdapter({ baseUrl: BASE, fetch });
    await adapter.init({ seed: 42 });
    // Init must have hit the network (session + /init) before we claim economics stay local.
    expect(calls.length).toBeGreaterThan(0);
    const afterInit = calls.length;

    const projector = new ViewModelProjector();
    projector.applySnapshot(SNAPSHOT);
    projector.setEconomics({ waste_cost: 99 });

    expect(calls.length).toBe(afterInit);
    const economicsPosts = calls.filter((c) => {
      if (c.body === null || typeof c.body !== "object") return false;
      return (
        "economics" in (c.body as Record<string, unknown>)
        || "waste_cost" in (c.body as Record<string, unknown>)
        || "pnl_series" in (c.body as Record<string, unknown>)
      );
    });
    expect(economicsPosts).toHaveLength(0);
    // HttpAdapter itself must not expose a network setEconomics.
    expect(
      "setEconomics" in adapter
        && typeof (adapter as { setEconomics?: unknown }).setEconomics === "function",
    ).toBe(false);
  });
});

/**
 * T-113 RED: studio chips call set_obs_scenario (live catch-up), not dirty-until-Reset.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import { HttpAdapter } from "./engine/httpAdapter";
import { PyodideAdapter } from "./engine/pyodideAdapter";
import type { Snapshot } from "./engine/types";

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTROLS_TS = join(HERE, "controls.ts");
const MAIN_TS = join(HERE, "react/studioLogic.ts");
const ADAPTER_TS = join(HERE, "engine/adapter.ts");
const HTTP_ADAPTER_TS = join(HERE, "engine/httpAdapter.ts");
const PYODIDE_ADAPTER_TS = join(HERE, "engine/pyodideAdapter.ts");

const FLAT_BELIEF = {
  L: 2,
  K: 4,
  lot_counts: [3, 3],
  age_marginals: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
  tau_grid: [0, 2.67, 5.33, 8],
};

function sampleSnapshot(overrides: Partial<Snapshot> = {}): Snapshot {
  return {
    seq: 0,
    episode_day: 0,
    belief: { ...FLAT_BELIEF, age_marginals: [...FLAT_BELIEF.age_marginals] },
    history: [],
    live_lots: [],
    pipeline: [],
    applied_config: { obs_scenario: "F1" },
    ...overrides,
  };
}

describe("T-113 chips call set_obs_scenario (not config_dirty for obs_scenario alone)", () => {
  it("controls chip click is not onConfigChange({ obs_scenario })", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).not.toMatch(
      /onConfigChange\(\s*\{\s*obs_scenario:\s*btn\.dataset\.obs/,
    );
    expect(src).toMatch(/set_obs_scenario|onObsScenario|onSetObsScenario/);
  });

  it("react/studioLogic.ts / adapter surface forwards set_obs_scenario", () => {
    const main = readFileSync(MAIN_TS, "utf8");
    const adapter = readFileSync(ADAPTER_TS, "utf8");
    expect(adapter).toMatch(/set_obs_scenario|setObsScenario/);
    expect(main).toMatch(/set_obs_scenario|setObsScenario/);
    expect(main).not.toMatch(
      /onConfigChange\(partial\).*obs_scenario[\s\S]{0,200}config_dirty/,
    );
  });

  it("locked copy says knowledge changes what the store sees", () => {
    const src = readFileSync(CONTROLS_TS, "utf8") + readFileSync(MAIN_TS, "utf8");
    expect(src.toLowerCase()).toMatch(/what the store sees/);
    expect(src.toLowerCase()).toMatch(/future orders/);
  });
});

describe("T-113 catch-up progress and chips disabled", () => {
  it("UI disables obs chips and shows catch-up progress while running", () => {
    const blob = readFileSync(CONTROLS_TS, "utf8") + readFileSync(MAIN_TS, "utf8");
    expect(blob).toMatch(/catch-?up/i);
    expect(blob).toMatch(/disabled/);
    expect(blob).toMatch(/progress/i);
  });

  it("Autopilot pauses during catch-up then resumes; next act follows the chip", () => {
    const main = readFileSync(MAIN_TS, "utf8");
    expect(main).toMatch(/catch-?up/i);
    expect(main).toMatch(/autopilot\.pause/);
    expect(main).toMatch(/set_obs_scenario|setObsScenario/);
    expect(main).toMatch(/autopilot\.(play|resume)|resume/);
  });
});

describe("T-113 HttpAdapter / PyodideAdapter forward set_obs_scenario", () => {
  it("HttpAdapter POSTs /sessions/{id}/set_obs_scenario", async () => {
    const calls: { url: string; method: string; body: unknown }[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      const method = (init?.method ?? "GET").toUpperCase();
      const body =
        typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
      calls.push({ url, method, body });
      if (url.endsWith("/sessions") && method === "POST") {
        return new Response(JSON.stringify({ session_id: "s1" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(sampleSnapshot()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const adapter = new HttpAdapter({
      baseUrl: "http://127.0.0.1:8000",
      fetch: fetchImpl,
    });
    await adapter.init({ seed: 1 });
    const fn =
      (adapter as unknown as { setObsScenario?: (id: string) => Promise<Snapshot> })
        .setObsScenario ??
      (adapter as unknown as { set_obs_scenario?: (id: string) => Promise<Snapshot> })
        .set_obs_scenario;
    expect(typeof fn).toBe("function");
    await fn!.call(adapter, "F2");
    const hit = calls.find((c) => c.url.includes("set_obs_scenario"));
    expect(hit).toBeDefined();
    expect(hit?.method).toBe("POST");
    expect(hit?.body).toEqual(expect.objectContaining({ obs_scenario: "F2" }));
  });

  it("PyodideAdapter RPC method is set_obs_scenario", async () => {
    class FakeWorker {
      static instances: FakeWorker[] = [];
      posted: unknown[] = [];
      onmessage: ((ev: MessageEvent) => void) | null = null;
      constructor(_url: string | URL, _opts?: WorkerOptions) {
        FakeWorker.instances.push(this);
      }
      postMessage(data: unknown): void {
        this.posted.push(data);
        queueMicrotask(() => {
          const req = JSON.parse(String(data)) as { id: string; method: string };
          this.onmessage?.({
            data: JSON.stringify({
              id: req.id,
              ok: true,
              result: sampleSnapshot(),
            }),
          } as MessageEvent);
        });
      }
      terminate(): void {}
      addEventListener(type: string, listener: EventListenerOrEventListenerObject): void {
        if (type === "message") {
          this.onmessage = listener as (ev: MessageEvent) => void;
        }
      }
      removeEventListener(): void {}
    }
    FakeWorker.instances = [];
    vi.stubGlobal(
      "Worker",
      class extends FakeWorker {
        constructor(url: string | URL, opts?: WorkerOptions) {
          super(url, opts);
        }
      },
    );
    try {
      const adapter = new PyodideAdapter({
        workerUrl: "/worker.js",
        wheelUrl: "https://example.test/pkg.whl",
      });
      const fn =
        (adapter as unknown as { setObsScenario?: (id: string) => Promise<Snapshot> })
          .setObsScenario ??
        (adapter as unknown as { set_obs_scenario?: (id: string) => Promise<Snapshot> })
          .set_obs_scenario;
      expect(typeof fn).toBe("function");
      await fn!.call(adapter, "F1s");
      const worker = FakeWorker.instances[0]!;
      const payloads = worker.posted.map(
        (p) => JSON.parse(String(p)) as { method: string; params?: Record<string, unknown> },
      );
      const msg = payloads.find((p) => p.method === "set_obs_scenario");
      expect(msg).toBeDefined();
      expect(msg?.params?.obs_scenario).toBe("F1s");
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("httpAdapter.ts and pyodideAdapter.ts mention set_obs_scenario", () => {
    expect(readFileSync(HTTP_ADAPTER_TS, "utf8")).toMatch(/set_obs_scenario/);
    expect(readFileSync(PYODIDE_ADAPTER_TS, "utf8")).toMatch(/set_obs_scenario/);
  });
});

/**
 * T-089 RED: Studio ScenarioId ladder (P0|P1|F1|F1s|F2a|F2), locked chip copy,
 * dirty-until-reset, main.ts passes staged config, mock drops P2.
 * Ticket A chart rebin is out of scope.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "./mock/generate";
import { MockAdapter } from "./mock/adapter";
import { HttpAdapter } from "./engine/httpAdapter";
import { PyodideAdapter } from "./engine/pyodideAdapter";
import { ViewModelProjector } from "./engine/projector";
import type { DayDelta, Snapshot } from "./engine/types";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_SRC = HERE;
const WEB_ROOT = join(HERE, "..");
const REPO_ROOT = join(WEB_ROOT, "..");
const CONTROLS_TS = join(WEB_SRC, "controls.ts");
const TYPES_TS = join(WEB_SRC, "types.ts");
const MAIN_TS = join(WEB_SRC, "main.ts");
const GENERATE_TS = join(WEB_SRC, "mock/generate.ts");
const MOCK_ADAPTER_TS = join(WEB_SRC, "mock/adapter.ts");
const BACKLOG = join(REPO_ROOT, ".team/backlog.md");

const LADDER = ["P0", "P1", "F1", "F1s", "F2a", "F2"] as const;

const LOCKED_COPY: Record<
  (typeof LADDER)[number],
  { title: string; description: string }
> = {
  P0: {
    title: "Books only",
    description: "Receipts and POS totals only — no daily waste.",
  },
  P1: {
    title: "Shrink gun",
    description: "Adds storewide daily waste totals.",
  },
  F1: {
    title: "Lot ID at POS",
    description: "Sales broken out by lot.",
  },
  F1s: {
    title: "Lot ID on shrink",
    description: "Waste broken out by lot.",
  },
  F2a: {
    title: "Pack date on ASN",
    description: "Narrows the arrival-age prior only.",
  },
  F2: {
    title: "Age at receipt",
    description: "Measured age at receipt plus rich lot maps.",
  },
};

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
    ...overrides,
  };
}

function sampleDelta(): DayDelta {
  return {
    seq: 1,
    episode_day: 0,
    day: {
      day: 0,
      lots: [],
      sales_total: 10,
      waste_total: 1,
      demand: 12,
      order_qty: 8,
      arrivals: 8,
      stockout: 0,
      age_at_receipt: 1,
    },
    drop_oldest: false,
    belief: { ...FLAT_BELIEF, age_marginals: [...FLAT_BELIEF.age_marginals] },
    live_lots: [],
    pipeline: [],
  };
}

function walkTsFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.endsWith(".test.ts")) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) out.push(...walkTsFiles(p));
    else if (name.endsWith(".ts") || name.endsWith(".tsx")) out.push(p);
  }
  return out;
}

describe("T-089 studio observation chips (ladder + locked copy)", () => {
  it("chip row data-obs ids are exactly P0|P1|F1|F1s|F2a|F2 in order", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    const ids = [...src.matchAll(/data-obs="([^"]+)"/g)].map((m) => m[1]);
    expect(ids).toEqual([...LADDER]);
  });

  it("controls expose locked title + description for every ScenarioId", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    for (const id of LADDER) {
      const { title, description } = LOCKED_COPY[id];
      expect(src, `missing title for ${id}`).toContain(title);
      expect(src, `missing description for ${id}`).toContain(description);
    }
  });

  it("no P2 chip, type literal, or mock blur branch remains under web/src", () => {
    const offenders: string[] = [];
    for (const file of walkTsFiles(WEB_SRC)) {
      const text = readFileSync(file, "utf8");
      const rel = relative(WEB_SRC, file);
      // Scenario / chip / blur uses of P2 (not ADR comments in tests we skip).
      if (/data-obs="P2"/.test(text)) offenders.push(`${rel}: data-obs P2`);
      if (/ObsScenario\s*=\s*"[^"]*"\s*\|\s*"[^"]*"\s*\|\s*"P2"/.test(text)) {
        offenders.push(`${rel}: ObsScenario includes P2`);
      }
      if (/ScenarioId\s*=[\s\S]*?"P2"/.test(text) && /export type ScenarioId/.test(text)) {
        offenders.push(`${rel}: ScenarioId includes P2`);
      }
      if (/scenario\s*===\s*"P2"|scenario\s*==\s*"P2"/.test(text)) {
        offenders.push(`${rel}: P2 blur/branch`);
      }
      if (/"P2"\s*\||"P0"\s*\|\s*"P1"\s*\|\s*"P2"/.test(text)) {
        // Narrow: old three-rung union.
        if (/ObsScenario|ScenarioId|"P0"\s*\|\s*"P1"\s*\|\s*"P2"/.test(text)) {
          offenders.push(`${rel}: P0|P1|P2 union`);
        }
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });
});

describe("T-089 ScenarioId type + default P1", () => {
  it("types.ts exports ScenarioId as the six-rung ladder (prefer delete ObsScenario)", () => {
    const src = readFileSync(TYPES_TS, "utf8");
    expect(src).toMatch(/export\s+type\s+ScenarioId\s*=/);
    for (const id of LADDER) {
      expect(src).toContain(`"${id}"`);
    }
    // Must not keep the fake three-rung ObsScenario as the primary type.
    expect(src).not.toMatch(
      /export\s+type\s+ObsScenario\s*=\s*"P0"\s*\|\s*"P1"\s*\|\s*"P2"/,
    );
    expect(src).toMatch(/obs_scenario:\s*ScenarioId/);
  });

  it("DEFAULT_SIM_CONFIG.obs_scenario remains P1", () => {
    expect(DEFAULT_SIM_CONFIG.obs_scenario).toBe("P1");
  });
});

describe("T-113 obs_scenario is live; not config_dirty until Reset (supersedes T-089 apply path)", () => {
  it("staging obs_scenario alone does not set config_dirty", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 14,
      config: { ...DEFAULT_SIM_CONFIG },
    });
    projector.applySnapshot(sampleSnapshot());
    projector.markConfigApplied();
    expect(projector.getViewModel().config_dirty).toBe(false);

    const staged = projector.setConfig({
      obs_scenario: "F2" as typeof DEFAULT_SIM_CONFIG.obs_scenario,
    });
    expect(staged.config.obs_scenario).toBe("F2");
    expect(staged.config_dirty).toBe(false);

    const afterAdvance = projector.applyDelta(sampleDelta());
    expect(afterAdvance.config_dirty).toBe(false);
    expect(afterAdvance.config.obs_scenario).toBe("F2");
  });

  it("staging other SimConfig knobs still sets config_dirty until Reset", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 14,
      config: { ...DEFAULT_SIM_CONFIG },
    });
    projector.markConfigApplied();
    projector.setConfig({ case_size: DEFAULT_SIM_CONFIG.case_size + 1 });
    expect(projector.getViewModel().config_dirty).toBe(true);
    const cleared = projector.markConfigApplied();
    expect(cleared.config_dirty).toBe(false);
  });
});

describe("T-089 main.ts passes staged config into adapter.init/reset", () => {
  it("bootstrap calls adapter.init with a config argument (not bare init())", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).not.toMatch(/adapter\.init\s*\(\s*\)/);
    expect(src).toMatch(/adapter\.init\s*\(\s*[^)]+/);
  });

  it("Reset calls adapter.reset with staged config (not bare reset())", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).not.toMatch(/adapter\.reset\s*\(\s*\)/);
    expect(src).toMatch(/adapter\.reset\s*\(\s*[^)]+/);
    // Belief-chart mounting must not be the vehicle for this AC.
    expect(src).toMatch(/projector\.applySnapshot/);
  });
});

describe("T-089 HTTP / Pyodide / mock forward obs_scenario; mock drops P2", () => {
  it("HttpAdapter init/reset body includes obs_scenario when provided", async () => {
    const calls: { url: string; body: unknown }[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      const body =
        typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
      calls.push({ url, body });
      if (url.endsWith("/sessions") && (init?.method ?? "GET").toUpperCase() === "POST") {
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
    await adapter.init({ obs_scenario: "F1", seed: 1 });
    await adapter.reset({ obs_scenario: "F2a", seed: 1 });

    const initCall = calls.find((c) => c.url.includes("/init"));
    const resetCall = calls.find((c) => c.url.includes("/reset"));
    expect(initCall?.body).toEqual(
      expect.objectContaining({
        config: expect.objectContaining({ obs_scenario: "F1" }),
      }),
    );
    expect(resetCall?.body).toEqual(
      expect.objectContaining({
        config: expect.objectContaining({ obs_scenario: "F2a" }),
      }),
    );
  });

  it("PyodideAdapter init/reset RPC params include obs_scenario in config", async () => {
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
          const req = JSON.parse(String(data)) as {
            id: string;
            method: string;
          };
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
      await adapter.init({ obs_scenario: "F1s" });
      await adapter.reset({ obs_scenario: "F2" });
      const worker = FakeWorker.instances[0]!;
      const payloads = worker.posted.map((p) => JSON.parse(String(p)) as {
        method: string;
        params?: { config?: Record<string, unknown> };
      });
      const initMsg = payloads.find((p) => p.method === "init");
      const resetMsg = payloads.find((p) => p.method === "reset");
      expect(initMsg?.params?.config?.obs_scenario).toBe("F1s");
      expect(resetMsg?.params?.config?.obs_scenario).toBe("F2");
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("mock generate/adapter accept the six ScenarioIds and drop P2 blur branch", async () => {
    const gen = readFileSync(GENERATE_TS, "utf8");
    const mock = readFileSync(MOCK_ADAPTER_TS, "utf8");
    expect(gen).not.toMatch(/scenario\s*===\s*"P2"/);
    expect(mock).not.toMatch(/scenario\s*===\s*"P2"/);

    const adapter = new MockAdapter(7);
    for (const id of LADDER) {
      const snap = await adapter.init({
        obs_scenario: id as typeof DEFAULT_SIM_CONFIG.obs_scenario,
      });
      expect(snap.applied_config?.obs_scenario ?? id).toBeDefined();
      // Must not throw on any ladder id.
      await adapter.reset({
        obs_scenario: id as typeof DEFAULT_SIM_CONFIG.obs_scenario,
      });
    }
  });
});

describe("T-089 SCN-P2 stays Out (web + backlog language)", () => {
  it("backlog still says do not reopen SCN-P2", () => {
    expect(existsSync(BACKLOG)).toBe(true);
    const text = readFileSync(BACKLOG, "utf8");
    expect(text).toMatch(/SCN-P2/);
    expect(text.toLowerCase()).toMatch(/do not reopen/);
  });

  it("controls chip row has no P2 button", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).not.toMatch(/data-obs="P2"/);
  });
});

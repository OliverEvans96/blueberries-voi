/**
 * Engine ready-chip: Loading (yellow) until adapter.init() settles,
 * Ready (green) on success, Failed (red) on reject.
 * Ready is NOT Worker construction — only a finished init RPC.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WasmAdapter } from "./wasmAdapter";
import {
  applyEngineStatusChip,
  createEngineStatusTracker,
  engineStatusChip,
  type EngineStatusKind,
  type EngineStatusTarget,
} from "./engineStatus";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_SRC = join(HERE, "..");
const LOGIC_TS = join(WEB_SRC, "react/studioLogic.ts");
const LAYOUT_TS = join(WEB_SRC, "react/StudioLayout.tsx");
const STYLES_CSS = join(WEB_SRC, "styles.css");
const WASM_ADAPTER_TS = join(HERE, "wasmAdapter.ts");

const SAMPLE_SNAPSHOT = {
  seq: 0,
  episode_day: 0,
  belief: {
    L: 2,
    K: 4,
    lot_counts: [3.6, 3.32],
    f_marginals: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
    f_grid: [0.125, 0.375, 0.625, 0.875],
  },
  history: [],
  live_lots: [],
  pipeline: [],
};

/** Holds `init` until `releaseInit` — Worker construction must not look ready. */
class HoldInitWorker {
  static instances: HoldInitWorker[] = [];
  readonly url: string | URL;
  readonly posted: unknown[] = [];
  private readonly listeners = new Map<string, Set<(ev: MessageEvent) => void>>();
  private heldInit: { id: string } | null = null;

  constructor(url: string | URL, _opts?: WorkerOptions) {
    this.url = url;
    HoldInitWorker.instances.push(this);
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
    let request: { id?: string; method?: string };
    try {
      request = typeof data === "string" ? JSON.parse(data) : (data as typeof request);
    } catch {
      return;
    }
    const id = request.id != null ? String(request.id) : "";
    if (request.method === "init") {
      this.heldInit = { id };
      return;
    }
    this.emit(JSON.stringify({ id, ok: true, result: { ready: true } }));
  }

  terminate(): void {
    /* no-op */
  }

  releaseInit(ok: boolean, message = "wasm init failed"): void {
    if (!this.heldInit) throw new Error("no held init");
    const { id } = this.heldInit;
    this.heldInit = null;
    if (ok) {
      this.emit(JSON.stringify({ id, ok: true, result: SAMPLE_SNAPSHOT }));
      return;
    }
    this.emit(
      JSON.stringify({
        id,
        ok: false,
        error: { type: "InitError", message },
      }),
    );
  }

  private emit(payload: string): void {
    const ev = { data: payload } as MessageEvent;
    for (const fn of this.listeners.get("message") ?? []) {
      queueMicrotask(() => fn(ev));
    }
  }
}

function installHoldInitWorker(): void {
  HoldInitWorker.instances = [];
  vi.stubGlobal(
    "Worker",
    class extends HoldInitWorker {
      constructor(url: string | URL, opts?: WorkerOptions) {
        super(url, opts);
      }
    },
  );
}

function fakeChipEl(initial: EngineStatusKind = "loading"): EngineStatusTarget & {
  label: { textContent: string | null };
} {
  const label = { textContent: engineStatusChip(initial).label as string | null };
  const dataset: { status?: string } = { status: initial };
  return {
    dataset,
    querySelector(sel: string) {
      if (sel === ".engine-status-label") return label;
      return null;
    },
    label,
  };
}

describe("engine status chip copy + dots", () => {
  it("loading is yellow + Loading (not Ready)", () => {
    const chip = engineStatusChip("loading");
    expect(chip.label).toBe("Loading");
    expect(chip.status).toBe("loading");
    expect(chip.dot).toBe("yellow");
    expect(chip.label).not.toBe("Ready");
  });

  it("ready is green + Ready after a finished init, not Worker construction", () => {
    const chip = engineStatusChip("ready");
    expect(chip.label).toBe("Ready");
    expect(chip.status).toBe("ready");
    expect(chip.dot).toBe("green");
  });

  it("error is red + short Failed label", () => {
    const chip = engineStatusChip("error");
    expect(chip.label).toBe("Failed");
    expect(chip.status).toBe("error");
    expect(chip.dot).toBe("red");
  });

  it("mock loading copy may say Connecting; wasm stays Loading", () => {
    expect(engineStatusChip("loading", "wasm").label).toBe("Loading");
    expect(engineStatusChip("loading", "mock").label).toMatch(/Connecting|Loading/);
    expect(engineStatusChip("ready", "wasm").label).toBe("Ready");
  });
});

describe("engine status tracker follows init, not Worker construction", () => {
  beforeEach(() => {
    installHoldInitWorker();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stays loading after new Worker / WasmAdapter until init RPC succeeds", async () => {
    const tracker = createEngineStatusTracker("loading");
    expect(tracker.get()).toBe("loading");

    const adapter = new WasmAdapter({
      workerUrl: "/packaging/wasm/worker.js",
      pkgUrl: "/packaging/wasm/pkg/voi_wasm_bg.wasm",
    });
    expect(HoldInitWorker.instances.length).toBeGreaterThanOrEqual(1);
    expect(tracker.get()).toBe("loading");

    const pending = tracker.follow(adapter.init({}));
    expect(tracker.get()).toBe("loading");

    HoldInitWorker.instances[0]!.releaseInit(true);
    await pending;
    expect(tracker.get()).toBe("ready");
  });

  it("turns error when init rejects (wasm bind / worker failure)", async () => {
    const tracker = createEngineStatusTracker("loading");
    const adapter = new WasmAdapter({
      workerUrl: "/packaging/wasm/worker.js",
      pkgUrl: "/packaging/wasm/pkg/voi_wasm_bg.wasm",
    });
    const pending = tracker.follow(adapter.init({}));
    HoldInitWorker.instances[0]!.releaseInit(false, "Failed to fetch wasm module");
    await expect(pending).rejects.toThrow(/wasm|InitError/i);
    expect(tracker.get()).toBe("error");
  });

  it("subscribe notifies listeners on each transition", async () => {
    const tracker = createEngineStatusTracker("loading");
    const seen: EngineStatusKind[] = [];
    const unsub = tracker.subscribe((kind) => {
      seen.push(kind);
    });
    expect(seen).toEqual(["loading"]);
    tracker.set("ready");
    expect(seen).toEqual(["loading", "ready"]);
    tracker.set("error");
    expect(seen).toEqual(["loading", "ready", "error"]);
    unsub();
    tracker.set("loading");
    expect(seen).toEqual(["loading", "ready", "error"]);
  });
});

describe("applyEngineStatusChip mutates a node-like target (no jsdom)", () => {
  it("writes data-status and label for loading → ready → error", () => {
    const el = fakeChipEl("loading");
    expect(el.dataset.status).toBe("loading");
    expect(el.label.textContent).toBe("Loading");

    applyEngineStatusChip(el, "ready");
    expect(el.dataset.status).toBe("ready");
    expect(el.label.textContent).toBe("Ready");

    applyEngineStatusChip(el, "error");
    expect(el.dataset.status).toBe("error");
    expect(el.label.textContent).toBe("Failed");
  });
});

describe("studio wires the chip in the header and follows bootstrap init", () => {
  it("StudioLayout hero includes #engine-status starting as Loading", () => {
    const src = readFileSync(LAYOUT_TS, "utf8");
    expect(src).toMatch(/id="engine-status"/);
    expect(src).toMatch(/data-status="loading"/);
    expect(src).toMatch(/engine-status-label">Loading</);
    expect(src).toMatch(/engine-status-dot/);
    const hero = src.match(/<header className="hero">[\s\S]*?<\/header>/);
    expect(hero, "expected hero header markup").toBeTruthy();
    expect(hero![0]).toMatch(/id="engine-status"/);
  });

  it("bootstrap maps successful init to ready and failed init to error", () => {
    const src = readFileSync(LOGIC_TS, "utf8");
    expect(src).toMatch(/createEngineStatusTracker|applyEngineStatusChip/);
    const bootstrap = src.match(/async function bootstrap[\s\S]*?\n\}/);
    expect(bootstrap, "expected bootstrap() in react/studioLogic.ts").toBeTruthy();
    expect(bootstrap![0]).toMatch(/follow\(|applyEngineStatusChip/);
    expect(bootstrap![0]).toMatch(/adapter\.init/);
    expect(src).toMatch(/reportStudioAdapterError/);
    const beforeInit = src.slice(0, src.indexOf("adapter.init"));
    expect(beforeInit).not.toMatch(/set\(\s*["']ready["']\s*\)/);
    expect(beforeInit).not.toMatch(/applyEngineStatusChip\([^)]*["']ready["']/);
  });

  it("styles.css paints yellow / green / red dots for the three states", () => {
    const css = readFileSync(STYLES_CSS, "utf8");
    expect(css).toMatch(/\.engine-status/);
    expect(css).toMatch(/\.engine-status-dot/);
    expect(css).toMatch(/data-status=["']loading["']|\[data-status=["']loading["']\]/);
    expect(css).toMatch(/data-status=["']ready["']|\[data-status=["']ready["']\]/);
    expect(css).toMatch(/data-status=["']error["']|\[data-status=["']error["']\]/);
    expect(css).toMatch(/#c9a227|#b8860b|#e6b422|#d4a017|#c4a000/i);
    expect(css).toMatch(/#2f6b4f|--profit/i);
    expect(css).toMatch(/#c46a3a|--spoil/i);
  });

  it("wasmAdapter init path is not rewritten by the status module", () => {
    const adapterSrc = readFileSync(WASM_ADAPTER_TS, "utf8");
    const statusSrc = readFileSync(join(HERE, "engineStatus.ts"), "utf8");
    expect(statusSrc).not.toMatch(/micropip|loadPyodide|pyodide/i);
    expect(statusSrc).not.toMatch(/importScripts/);
    expect(adapterSrc).toMatch(/\binit\b/);
  });
});

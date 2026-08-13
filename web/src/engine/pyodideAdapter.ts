/**
 * PyodideAdapter — production EngineAdapter (T-055).
 *
 * Hosts the packaging/pyodide worker from the main thread. Forwards RPC
 * ({id, method, params} → Snapshot / DayDelta). Passes Release/slim wheel URL
 * for micropip.install. Default budgets = DEMO_BUDGETS. Never holds a PyProxy
 * on the main thread — only plain data / JSON.
 */

import type { EngineAdapter } from "./adapter";
import type {
  ActOpts,
  DayDelta,
  EngineConfig,
  Snapshot,
} from "./types";

/** Dialed browser demo budgets (ADR 0099 / DEMO_BUDGETS). */
export type DemoBudgets = {
  n_particles: number;
  H: number;
  n_rollout_paths: number;
  candidate_case_radius: number;
};

/** ADR 0099 caps — default when `budgets` is omitted from constructor opts. */
export const DEFAULT_DEMO_BUDGETS: DemoBudgets = {
  n_particles: 200,
  H: 7,
  n_rollout_paths: 2,
  candidate_case_radius: 1,
};

export type PyodideAdapterOpts = {
  workerUrl: string;
  wheelUrl: string;
  budgets?: DemoBudgets;
};

type RpcRequest = {
  id: string;
  method: string;
  params?: Record<string, unknown>;
};

type RpcOk = { id: string; ok: true; result: unknown };
type RpcErr = {
  id: string;
  ok: false;
  error: { type?: string; message?: string };
};
type RpcResponse = RpcOk | RpcErr;

function withWheelQuery(workerUrl: string, wheelUrl: string): string {
  const sep = workerUrl.includes("?") ? "&" : "?";
  return `${workerUrl}${sep}wheelUrl=${encodeURIComponent(wheelUrl)}`;
}

/**
 * Production EngineAdapter: forwards init / step / step_n / reset / act to the
 * Pyodide worker. Main thread sees only plain JSON / Snapshot / DayDelta.
 */
export class PyodideAdapter implements EngineAdapter {
  private readonly worker: Worker;
  private readonly budgets: DemoBudgets;
  private readonly wheelUrl: string;
  private nextId = 0;
  private readonly pending = new Map<
    string,
    { resolve: (v: unknown) => void; reject: (e: Error) => void }
  >();
  private readonly onMessage: (ev: MessageEvent) => void;
  private readonly onError: (ev: ErrorEvent) => void;

  constructor(opts: PyodideAdapterOpts) {
    this.budgets = opts.budgets ?? { ...DEFAULT_DEMO_BUDGETS };
    this.wheelUrl = opts.wheelUrl;
    const url = withWheelQuery(opts.workerUrl, opts.wheelUrl);
    this.worker = new Worker(url, { type: "module" });

    this.onMessage = (ev: MessageEvent) => {
      let resp: RpcResponse;
      try {
        const raw = ev.data;
        resp =
          typeof raw === "string"
            ? (JSON.parse(raw) as RpcResponse)
            : (raw as RpcResponse);
      } catch (err) {
        // Unmatched parse failure — reject all waiters if we cannot route.
        const message = err instanceof Error ? err.message : String(err);
        for (const [, waiter] of this.pending) {
          waiter.reject(new Error(`RPC response parse failed: ${message}`));
        }
        this.pending.clear();
        return;
      }
      const id = resp.id != null ? String(resp.id) : "";
      const waiter = this.pending.get(id);
      if (!waiter) return;
      this.pending.delete(id);
      if (!resp.ok) {
        const err = resp.error ?? {};
        waiter.reject(
          new Error(`${err.type ?? "RpcError"}: ${err.message ?? "unknown"}`),
        );
        return;
      }
      waiter.resolve(resp.result);
    };

    this.onError = (ev: ErrorEvent) => {
      const message = ev.message || "Worker error";
      for (const [, waiter] of this.pending) {
        waiter.reject(new Error(message));
      }
      this.pending.clear();
    };

    this.worker.addEventListener("message", this.onMessage);
    this.worker.addEventListener("error", this.onError);

    // Advertise Release/slim wheel to the worker (FakeWorker accepts configure;
    // production worker may ignore unknown methods — URL query also carries it).
    void this.call("configure", { wheelUrl: opts.wheelUrl }).catch(() => {
      /* optional */
    });
  }

  private call(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    const id = `rpc-${++this.nextId}`;
    const request: RpcRequest = { id, method, params };
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage(JSON.stringify(request));
    });
  }

  private mergeConfig(config?: EngineConfig): Record<string, unknown> {
    const merged: Record<string, unknown> = {
      ...this.budgets,
      ...(config ?? {}),
    };
    return merged;
  }

  async init(config?: EngineConfig): Promise<Snapshot> {
    const merged = this.mergeConfig(config);
    const seed = merged.seed;
    const params: Record<string, unknown> = { config: merged };
    if (seed !== undefined) {
      params.seed = seed;
    }
    // Ensure wheelUrl is present on the first engine RPC as well.
    params.wheelUrl = this.wheelUrl;
    return (await this.call("init", params)) as Snapshot;
  }

  async step(order_qty: number): Promise<DayDelta> {
    return (await this.call("step", { order_qty })) as DayDelta;
  }

  async step_n(orders: number[]): Promise<DayDelta[]> {
    return (await this.call("step_n", { orders })) as DayDelta[];
  }

  async reset(config?: EngineConfig): Promise<Snapshot> {
    const params: Record<string, unknown> = {};
    if (config !== undefined) {
      const merged = this.mergeConfig(config);
      params.config = merged;
      if (merged.seed !== undefined) {
        params.seed = merged.seed;
      }
    }
    return (await this.call("reset", params)) as Snapshot;
  }

  async act(opts?: ActOpts): Promise<DayDelta> {
    return (await this.call("act", { ...(opts ?? {}) })) as DayDelta;
  }

  /** Tear down the worker (optional for hosts / smoke). */
  terminate(): void {
    this.worker.removeEventListener("message", this.onMessage);
    this.worker.removeEventListener("error", this.onError);
    this.worker.terminate();
    this.pending.clear();
  }
}

/**
 * Clear pass/fail smoke: construct PyodideAdapter against a Release/slim wheel
 * URL + packaging worker (Pyodide 314.0.4), then drive one init+step.
 *
 * Throws on failure. Returns `{ ok: true, snapshot, delta }` on success.
 */
export async function runPyodideAdapterSmoke(opts?: {
  workerUrl?: string;
  wheelUrl?: string;
}): Promise<{ ok: true; snapshot: Snapshot; delta: DayDelta }> {
  const workerUrl = opts?.workerUrl ?? "/packaging/pyodide/worker.js";
  const wheelUrl =
    opts?.wheelUrl ??
    "https://github.com/oliver/blueberries-voi/releases/download/v0.1.0/" +
      "blueberries_voi-0.1.0-py3-none-any.whl";
  const adapter = new PyodideAdapter({ workerUrl, wheelUrl });
  try {
    const snapshot = await adapter.init({});
    const delta = await adapter.step(1);
    if (snapshot == null || typeof snapshot !== "object") {
      throw new Error("smoke fail: init did not return a Snapshot");
    }
    if (delta == null || typeof delta !== "object") {
      throw new Error("smoke fail: step did not return a DayDelta");
    }
    return { ok: true, snapshot, delta };
  } finally {
    adapter.terminate();
  }
}

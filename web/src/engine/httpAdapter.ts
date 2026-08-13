/**
 * HttpAdapter — EngineAdapter over the Slice-2 ASGI session API (T-056).
 */

import type { EngineAdapter } from "./adapter";
import type { ActOpts, DayDelta, EngineConfig, Snapshot } from "./types";

export type HttpAdapterOptions = {
  /**
   * ASGI base URL (e.g. `http://127.0.0.1:8000`). When omitted, read
   * `import.meta.env.VITE_ENGINE_API_BASE_URL` (or `VITE_API_BASE_URL`).
   */
  baseUrl?: string;
  /** Injectable for contract tests; defaults to `globalThis.fetch`. */
  fetch?: typeof fetch;
};

type InitBody = { config: EngineConfig; seed?: number };
type ResetBody = { config?: EngineConfig; seed?: number };

function stripTrailingSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

function readEnvBaseUrl(): string | undefined {
  const fromMeta =
    import.meta.env.VITE_ENGINE_API_BASE_URL
    ?? import.meta.env.VITE_API_BASE_URL;
  if (typeof fromMeta === "string" && fromMeta.length > 0) {
    return fromMeta;
  }
  return undefined;
}

function splitConfigSeed(config?: EngineConfig): {
  config: EngineConfig;
  seed?: number;
} {
  if (config === undefined) {
    return { config: {} };
  }
  const { seed, ...rest } = config;
  if (typeof seed === "number") {
    return { config: rest, seed };
  }
  return { config: { ...config } };
}

/**
 * Dev EngineAdapter over the Slice-2 ASGI app (ADR 0100 / T-049).
 *
 * Session lifecycle (documented):
 * - **Create:** `POST /sessions` on construct or first `init`, stores `session_id`.
 * - **Reset:** `POST /sessions/{id}/reset` — same session, cold Snapshot.
 * - **Delete:** `dispose()` → `DELETE /sessions/{id}` (204); further calls error.
 *
 * Economics / PnL / ghost / heatmap never leave JS — use
 * `ViewModelProjector.setEconomics` (no HTTP).
 */
export class HttpAdapter implements EngineAdapter {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private sessionId: string | null = null;
  private disposed = false;

  constructor(opts: HttpAdapterOptions = {}) {
    const resolved = opts.baseUrl ?? readEnvBaseUrl();
    if (!resolved || resolved.length === 0) {
      throw new Error(
        "HttpAdapter requires baseUrl or VITE_ENGINE_API_BASE_URL / VITE_API_BASE_URL",
      );
    }
    this.baseUrl = stripTrailingSlash(resolved);
    this.fetchImpl = opts.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async init(config?: EngineConfig): Promise<Snapshot> {
    await this.ensureSession();
    const { config: cfg, seed } = splitConfigSeed(config);
    const body: InitBody = { config: cfg };
    if (seed !== undefined) {
      body.seed = seed;
    }
    return this.postJson<Snapshot>(`/sessions/${this.sessionId}/init`, body);
  }

  async step(order_qty: number): Promise<DayDelta> {
    await this.ensureSession();
    return this.postJson<DayDelta>(`/sessions/${this.sessionId}/step`, {
      order_qty,
    });
  }

  async step_n(orders: number[]): Promise<DayDelta[]> {
    await this.ensureSession();
    const wrapped = await this.postJson<{ deltas: DayDelta[] }>(
      `/sessions/${this.sessionId}/step_n`,
      { orders },
    );
    return wrapped.deltas;
  }

  async reset(config?: EngineConfig): Promise<Snapshot> {
    await this.ensureSession();
    const body: ResetBody = {};
    if (config !== undefined) {
      const { config: cfg, seed } = splitConfigSeed(config);
      body.config = cfg;
      if (seed !== undefined) {
        body.seed = seed;
      }
    }
    return this.postJson<Snapshot>(`/sessions/${this.sessionId}/reset`, body);
  }

  /** Optional EngineAdapter.act → POST /sessions/{id}/act */
  async act(opts?: ActOpts): Promise<DayDelta> {
    await this.ensureSession();
    const policy =
      opts && typeof opts.policy === "string" ? opts.policy : undefined;
    const budgets =
      opts && typeof opts.budgets === "object" && opts.budgets !== null
        ? (opts.budgets as Record<string, unknown>)
        : {};
    const body: { policy?: string; budgets: Record<string, unknown> } = {
      budgets,
    };
    if (policy !== undefined) {
      body.policy = policy;
    }
    return this.postJson<DayDelta>(`/sessions/${this.sessionId}/act`, body);
  }

  /** Destroy the server session (`DELETE /sessions/{id}` → 204). */
  async dispose(): Promise<void> {
    if (this.disposed || this.sessionId === null) {
      this.disposed = true;
      this.sessionId = null;
      return;
    }
    const id = this.sessionId;
    const res = await this.fetchImpl(`${this.baseUrl}/sessions/${id}`, {
      method: "DELETE",
    });
    this.disposed = true;
    this.sessionId = null;
    if (!res.ok && res.status !== 204) {
      const text = await res.text();
      throw new Error(`HttpAdapter dispose failed (${res.status}): ${text}`);
    }
  }

  private assertNotDisposed(): void {
    if (this.disposed) {
      throw new Error("HttpAdapter session has been disposed");
    }
  }

  private async ensureSession(): Promise<void> {
    this.assertNotDisposed();
    if (this.sessionId !== null) {
      return;
    }
    const res = await this.fetchImpl(`${this.baseUrl}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HttpAdapter create session failed (${res.status}): ${text}`);
    }
    const data = (await res.json()) as { session_id: string };
    this.sessionId = data.session_id;
  }

  private async postJson<T>(path: string, body: unknown): Promise<T> {
    this.assertNotDisposed();
    const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HttpAdapter ${path} failed (${res.status}): ${text}`);
    }
    return (await res.json()) as T;
  }
}

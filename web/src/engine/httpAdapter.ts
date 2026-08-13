/**
 * HttpAdapter — RED stub for T-056.
 * Implementer: fetch T-049 session routes; return Snapshot / DayDelta only.
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
  constructor(_opts: HttpAdapterOptions = {}) {
    /* implementer: resolve baseUrl from opts or env; optionally create session */
  }

  async init(_config?: EngineConfig): Promise<Snapshot> {
    // Stub: incomplete so RED contract tests fail on path/body/shape.
    return {} as Snapshot;
  }

  async step(_order_qty: number): Promise<DayDelta> {
    return {} as DayDelta;
  }

  async step_n(_orders: number[]): Promise<DayDelta[]> {
    return [];
  }

  async reset(_config?: EngineConfig): Promise<Snapshot> {
    return {} as Snapshot;
  }

  /** Optional EngineAdapter.act → POST /sessions/{id}/act */
  async act(_opts?: ActOpts): Promise<DayDelta> {
    return {} as DayDelta;
  }

  /** Destroy the server session (`DELETE /sessions/{id}` → 204). */
  async dispose(): Promise<void> {
    /* implementer */
  }
}

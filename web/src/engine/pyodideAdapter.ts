/**
 * PyodideAdapter — RED stub for T-055.
 *
 * Implementer: host the packaging/pyodide worker edge from the main thread.
 * Forward RPC ({id, method, params} → Snapshot / DayDelta). Pass Release/slim
 * wheel URL for micropip.install. Default budgets = DEMO_BUDGETS. Never hold a
 * PyProxy on the main thread — only plain data / JSON.
 */

import type { EngineAdapter } from "./adapter";
import type {
  ActOpts,
  DayDelta,
  EngineConfig,
  Snapshot,
} from "./types";

/** Dialed browser demo budgets (ADR 0097 / DEMO_BUDGETS). */
export type DemoBudgets = {
  n_particles: number;
  H: number;
  n_rollout_paths: number;
  candidate_case_radius: number;
};

/** ADR 0097 caps — default when `budgets` is omitted from constructor opts. */
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

/**
 * Production EngineAdapter: forwards init / step / step_n / reset / act to the
 * Pyodide worker. Main thread sees only plain JSON / Snapshot / DayDelta.
 */
export class PyodideAdapter implements EngineAdapter {
  constructor(_opts: PyodideAdapterOpts) {
    /* implementer: spawn Worker(opts.workerUrl), pass wheelUrl + budgets */
  }

  async init(_config?: EngineConfig): Promise<Snapshot> {
    // Stub: incomplete so RED tests fail on Snapshot shape / RPC forwarding.
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

  async act(_opts?: ActOpts): Promise<DayDelta> {
    return {} as DayDelta;
  }
}

/** Shared EngineAdapter contract (T-053 / T-054). */

import type {
  ActOpts,
  DayDelta,
  EngineConfig,
  Snapshot,
} from "./types";

/**
 * Host-facing engine boundary. Returns Snapshot / DayDelta only — never a full
 * ViewModel. Economics / PnL / ghost / heatmap stay in ViewModelProjector.
 */
export interface EngineAdapter {
  init(config?: EngineConfig): Promise<Snapshot>;
  step(order_qty: number): Promise<DayDelta>;
  step_n(orders: number[]): Promise<DayDelta[]>;
  reset(config?: EngineConfig): Promise<Snapshot>;
  act?(opts?: ActOpts): Promise<DayDelta>;
}

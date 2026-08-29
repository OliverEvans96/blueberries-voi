/** Shared EngineAdapter contract (T-053 / T-054). */

import type {
  ActOpts,
  DayDelta,
  EngineConfig,
  EventsResult,
  EventsWire,
  Snapshot,
  TradeoffForecastResult,
  TradeoffForecastWire,
} from "./types";

/** Wire aliases documented for adapter implementers (T-127). */
export type { TradeoffForecastWire, EventsWire };

/**
 * Host-facing engine boundary. Returns Snapshot / DayDelta only — never a full
 * ViewModel. Economics / PnL / heatmap stay in ViewModelProjector.
 */
export interface EngineAdapter {
  init(config?: EngineConfig): Promise<Snapshot>;
  step(order_qty: number): Promise<DayDelta>;
  step_n(orders: number[]): Promise<DayDelta[]>;
  reset(config?: EngineConfig): Promise<Snapshot>;
  act?(opts?: ActOpts): Promise<DayDelta>;
  setObsScenario?(obs_scenario: string): Promise<Snapshot>;
  set_obs_scenario?(obs_scenario: string): Promise<Snapshot>;
  setObsChannels?(channels: {
    code_type: string;
    scan_waste: boolean;
    delivery_history: string;
  }): Promise<Snapshot>;
  set_obs_channels?(channels: {
    code_type: string;
    scan_waste: boolean;
    delivery_history: string;
  }): Promise<Snapshot>;
  tradeoffForecast?(params?: {
    n_paths?: number;
    protection_days?: number;
  }): Promise<TradeoffForecastResult>;
  /** Events RPC envelope: `{ days: EventDayWire[] }`. */
  events?(params: { since_day: number }): Promise<EventsResult>;
}

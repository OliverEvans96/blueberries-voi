import type {
  BeliefGrid,
  Economics,
  SimConfig,
  StepInput,
  ViewModel,
} from "../types";
import {
  DEFAULT_ECONOMICS,
  DEFAULT_SIM_CONFIG,
  computePnL,
  createInitialState,
  generateBelief,
  snapCases,
  stepSimulation,
  type SimState,
} from "./generate";

function configsEqual(a: SimConfig, b: SimConfig): boolean {
  return (Object.keys(a) as (keyof SimConfig)[]).every((k) => a[k] === b[k]);
}

export class MockAdapter {
  private state: SimState;
  /** Live config used by Advance day; may differ from episode until Reset. */
  private config: SimConfig;
  private appliedConfig: SimConfig;
  private economics: Economics;
  private belief: BeliefGrid;

  constructor(seed = DEFAULT_SIM_CONFIG.seed) {
    this.config = { ...DEFAULT_SIM_CONFIG, seed };
    this.appliedConfig = { ...this.config };
    this.economics = { ...DEFAULT_ECONOMICS };
    this.state = createInitialState(this.config);
    this.belief = generateBelief(
      this.state.lots,
      this.state.rng,
      this.config.obs_scenario,
    );
  }

  init(): ViewModel {
    return this.toViewModel();
  }

  step(input: StepInput): ViewModel {
    const { state } = stepSimulation(this.state, input.order_qty, this.config);
    this.state = state;
    this.belief = generateBelief(
      this.state.lots,
      this.state.rng,
      this.config.obs_scenario,
    );
    return this.toViewModel();
  }

  setEconomics(next: Partial<Economics>): ViewModel {
    this.economics = { ...this.economics, ...next };
    return this.toViewModel();
  }

  /** Update sim knobs (does not regenerate history until reset). */
  setConfig(next: Partial<SimConfig>): ViewModel {
    this.config = { ...this.config, ...next };
    if (typeof next.case_size === "number") {
      this.config.case_size = Math.max(1, Math.round(next.case_size));
    }
    if (typeof next.lead_time === "number") {
      this.config.lead_time = Math.max(0, Math.round(next.lead_time));
    }
    if (typeof next.seed === "number") {
      this.config.seed = Math.round(next.seed);
    }
    // Belief scenario can update the current belief pane immediately
    if (next.obs_scenario != null) {
      this.belief = generateBelief(
        this.state.lots,
        this.state.rng,
        this.config.obs_scenario,
      );
    }
    return this.toViewModel();
  }

  /** Regenerate the episode from seed with the current config. */
  reset(): ViewModel {
    this.appliedConfig = { ...this.config };
    this.state = createInitialState(this.config);
    this.belief = generateBelief(
      this.state.lots,
      this.state.rng,
      this.config.obs_scenario,
    );
    return this.toViewModel();
  }

  getConfig(): SimConfig {
    return { ...this.config };
  }

  getEconomics(): Economics {
    return { ...this.economics };
  }

  snapOrder(qty: number): number {
    return snapCases(qty, this.config.case_size);
  }

  private toViewModel(): ViewModel {
    const { series, totals } = computePnL(this.state.history, this.economics);
    const pending = this.state.pendingOrders.reduce((s, o) => s + o.qty, 0);
    return {
      episode_day: this.state.day,
      window_days: this.config.window_days,
      history: this.state.history.map((d) => ({
        ...d,
        lots: d.lots.map((l) => ({ ...l })),
      })),
      economics: { ...this.economics },
      config: { ...this.config },
      config_dirty: !configsEqual(this.config, this.appliedConfig),
      pnl_series: series,
      pnl_totals: totals,
      belief: this.belief,
      case_size: this.config.case_size,
      pending_order: pending,
    };
  }
}

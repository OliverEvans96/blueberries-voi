import type { BeliefGrid, Economics, StepInput, ViewModel } from "../types";
import {
  MOCK_DEFAULTS,
  computePnL,
  createInitialState,
  generateBelief,
  stepSimulation,
  type SimState,
} from "./generate";

export class MockAdapter {
  private state: SimState;
  private economics: Economics;
  private belief: BeliefGrid;

  constructor(seed = 42) {
    this.state = createInitialState(seed);
    this.economics = { ...MOCK_DEFAULTS.economics };
    this.belief = generateBelief(this.state.lots, this.state.rng);
  }

  init(): ViewModel {
    return this.toViewModel();
  }

  step(input: StepInput): ViewModel {
    const { state } = stepSimulation(this.state, input.order_qty);
    this.state = state;
    this.belief = generateBelief(this.state.lots, this.state.rng);
    return this.toViewModel();
  }

  setEconomics(next: Partial<Economics>): ViewModel {
    this.economics = { ...this.economics, ...next };
    return this.toViewModel();
  }

  getEconomics(): Economics {
    return { ...this.economics };
  }

  private toViewModel(): ViewModel {
    const { series, totals } = computePnL(this.state.history, this.economics);
    const pending = this.state.pendingOrders.reduce((s, o) => s + o.qty, 0);
    return {
      episode_day: this.state.day,
      window_days: MOCK_DEFAULTS.WINDOW_DAYS,
      history: this.state.history.map((d) => ({
        ...d,
        lots: d.lots.map((l) => ({ ...l })),
      })),
      economics: { ...this.economics },
      pnl_series: series,
      pnl_totals: totals,
      belief: this.belief,
      case_size: MOCK_DEFAULTS.CASE_SIZE,
      pending_order: pending,
    };
  }
}

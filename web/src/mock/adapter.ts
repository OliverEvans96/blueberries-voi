import type {
  BeliefGrid,
  Day,
  DayPnL,
  Economics,
  EpisodeGhost,
  GhostDeltas,
  PipelineOrder,
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
  onHandInventory,
  snapCases,
  stepSimulation,
  survivalWeightedInventory,
  type SimState,
} from "./generate";

function configsEqual(a: SimConfig, b: SimConfig): boolean {
  return (Object.keys(a) as (keyof SimConfig)[]).every((k) => a[k] === b[k]);
}

function snapshotGhost(
  history: Day[],
  economics: Economics,
): EpisodeGhost {
  const { series } = computePnL(history, economics);
  let profitCum = 0;
  const points = history.map((d, i) => {
    const pnl = series[i]!;
    profitCum += pnl.profit;
    return {
      i,
      waste: d.waste_total,
      stockout: d.stockout,
      sales: d.sales_total,
      demand: d.demand,
      profit: pnl.profit,
      profit_cum: profitCum,
    };
  });
  return {
    series: points,
    waste_total: points.reduce((s, p) => s + p.waste, 0),
    stockout_total: points.reduce((s, p) => s + p.stockout, 0),
    profit_cum: profitCum,
    days: points.length,
  };
}

function ghostDeltas(
  history: Day[],
  pnl: DayPnL[],
  ghost: EpisodeGhost | null,
): GhostDeltas | null {
  if (!ghost || ghost.days === 0 || history.length === 0) return null;
  const waste = history.reduce((s, d) => s + d.waste_total, 0);
  const stockout = history.reduce((s, d) => s + d.stockout, 0);
  const profit = pnl.reduce((s, d) => s + d.profit, 0);
  const liveDays = history.length;
  return {
    waste_rate: waste / liveDays - ghost.waste_total / ghost.days,
    stockouts: stockout - ghost.stockout_total,
    profit_cum: profit - ghost.profit_cum,
  };
}

export class MockAdapter {
  private state: SimState;
  private config: SimConfig;
  private appliedConfig: SimConfig;
  private economics: Economics;
  private belief: BeliefGrid;
  private ghost: EpisodeGhost | null = null;

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

  setConfig(next: Partial<SimConfig>): ViewModel {
    this.config = { ...this.config, ...next };
    if (typeof next.case_size === "number") {
      this.config.case_size = Math.max(1, Math.round(next.case_size));
    }
    // Daily ordering: lead time fixed at 1 (not a user-facing knob)
    this.config.lead_time = 1;
    if (typeof next.seed === "number") {
      this.config.seed = Math.round(next.seed);
    }
    if (next.obs_scenario != null) {
      this.belief = generateBelief(
        this.state.lots,
        this.state.rng,
        this.config.obs_scenario,
      );
    }
    return this.toViewModel();
  }

  /** Snapshot prior episode as ghost, then regenerate from seed. */
  reset(): ViewModel {
    this.ghost = snapshotGhost(this.state.history, this.economics);
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

  private pipeline(): PipelineOrder[] {
    return this.state.pendingOrders
      .map((o) => ({
        qty: o.qty,
        arrive_on: o.arriveOn,
        days_until: o.arriveOn - this.state.day,
      }))
      .filter((o) => o.days_until >= 0)
      .sort((a, b) => a.days_until - b.days_until || a.arrive_on - b.arrive_on);
  }

  private toViewModel(): ViewModel {
    const { series, totals } = computePnL(this.state.history, this.economics);
    const pending = this.state.pendingOrders.reduce((s, o) => s + o.qty, 0);
    const live_lots = this.state.lots.map((l) => ({ ...l }));
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
      live_lots,
      on_hand: onHandInventory(live_lots),
      effective_inv: survivalWeightedInventory(live_lots, this.config),
      pipeline: this.pipeline(),
      ghost: this.ghost,
      ghost_deltas: ghostDeltas(this.state.history, series, this.ghost),
      case_size: this.config.case_size,
      pending_order: pending,
    };
  }
}

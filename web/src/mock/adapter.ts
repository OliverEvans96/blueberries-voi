import type { EngineAdapter } from "../engine/adapter";
import type {
  DayDelta,
  DemandSummary,
  EngineConfig,
  FlatBelief,
  ScheduleWire,
  Snapshot,
} from "../engine/types";
import type {
  Economics,
  Lot,
  PipelineOrder,
  ScenarioId,
  SimConfig,
  StepInput,
} from "../types";
import {
  DEFAULT_ECONOMICS,
  DEFAULT_SIM_CONFIG,
  createInitialState,
  snapCases,
  stepSimulation,
  type SimState,
} from "./generate";

/** Coherent OrderSchedule stubs when live engine is absent (T-085 / ADR 0111). */
const MOCK_SCHEDULE: ScheduleWire = {
  delivery_weekdays: [0, 2, 4],
  order_weekdays: [6, 1, 3],
  lead_time_days: 1,
  epoch: "2024-01-01",
};

/** Chart-ready demand summary stub (~FreshNet scale 30 × DOW factors). */
const MOCK_DEMAND_SUMMARY: DemandSummary = {
  scale_mu: 30,
  dow_means: [29.1228, 30.2511, 27.86433, 25.81527, 27.76173, 33.8766, 35.30814],
};

function configsEqual(a: SimConfig, b: SimConfig): boolean {
  return (Object.keys(a) as (keyof SimConfig)[]).every((k) => a[k] === b[k]);
}

function beliefBlur(scenario: ScenarioId): number {
  if (scenario === "P0") return 1.6;
  if (scenario === "F2") return 0.55;
  if (scenario === "F2a") return 0.7;
  if (scenario === "F1s") return 0.85;
  if (scenario === "F1") return 0.95;
  return 1; // P1
}

/** Flat L×K belief from live lots (fake physics; JS heatmap derives density). */
export function generateFlatBelief(
  lots: Lot[],
  rng: () => number,
  scenario: ScenarioId = "P1",
  K = 12,
): FlatBelief {
  const L = lots.length;
  if (L === 0) {
    return {
      L: 0,
      K,
      lot_counts: [],
      age_marginals: [],
      tau_grid: Array.from({ length: K }, (_, i) => i),
    };
  }

  const lot_counts = lots.map((l) => l.n);
  const maxTau = Math.max(8, ...lots.map((l) => l.tau));
  const tau_grid = Array.from(
    { length: K },
    (_, i) => (i / Math.max(1, K - 1)) * maxTau,
  );
  const blur = beliefBlur(scenario);
  const age_marginals: number[] = [];

  for (let l = 0; l < L; l++) {
    const tau = lots[l]!.tau;
    const row: number[] = [];
    let sum = 0;
    for (let k = 0; k < K; k++) {
      const d = (tau_grid[k]! - tau) / blur;
      const mass = Math.exp(-(d * d) / 2) * (0.75 + 0.5 * rng());
      row.push(mass);
      sum += mass;
    }
    for (const m of row) {
      age_marginals.push(sum > 0 ? m / sum : 1 / K);
    }
  }

  return { L, K, lot_counts, age_marginals, tau_grid };
}

/**
 * Mock engine speaking Snapshot / DayDelta (EngineAdapter). Presentation
 * (PnL / economics / ghost / heatmap) stays in ViewModelProjector.
 */
export class MockAdapter implements EngineAdapter {
  private state: SimState;
  private config: SimConfig;
  private appliedConfig: SimConfig;
  /** Kept for studio getEconomics; projector owns live economics for PnL. */
  private economics: Economics;
  private flatBelief: FlatBelief;
  private seq = 0;

  constructor(seed = DEFAULT_SIM_CONFIG.seed) {
    this.config = { ...DEFAULT_SIM_CONFIG, seed };
    this.appliedConfig = { ...this.config };
    this.economics = { ...DEFAULT_ECONOMICS };
    this.state = createInitialState(this.config);
    this.flatBelief = generateFlatBelief(
      this.state.lots,
      this.state.rng,
      this.config.obs_scenario,
    );
  }

  async init(config?: EngineConfig): Promise<Snapshot> {
    if (config) {
      this.applyConfigPartial(config);
    }
    this.appliedConfig = { ...this.config };
    this.state = createInitialState(this.config);
    this.flatBelief = generateFlatBelief(
      this.state.lots,
      this.state.rng,
      this.config.obs_scenario,
    );
    this.seq = 0;
    return this.toSnapshot();
  }

  async step(order_qty: number): Promise<DayDelta> {
    return this.stepOnce(order_qty);
  }

  async step_n(orders: number[]): Promise<DayDelta[]> {
    const out: DayDelta[] = [];
    for (const qty of orders) {
      out.push(this.stepOnce(qty));
    }
    return out;
  }

  async reset(config?: EngineConfig): Promise<Snapshot> {
    if (config) {
      this.applyConfigPartial(config);
    }
    this.appliedConfig = { ...this.config };
    this.state = createInitialState(this.config);
    this.flatBelief = generateFlatBelief(
      this.state.lots,
      this.state.rng,
      this.config.obs_scenario,
    );
    this.seq = 0;
    return this.toSnapshot();
  }

  /**
   * Studio helper: stage knobs on the mock physics. Returns a Snapshot of the
   * current engine fields (no presentation keys) so the projector can patch.
   */
  setConfig(next: Partial<SimConfig>): Snapshot {
    this.applyConfigPartial(next);
    if (next.obs_scenario != null) {
      this.flatBelief = generateFlatBelief(
        this.state.lots,
        this.state.rng,
        this.config.obs_scenario,
      );
    }
    return this.toSnapshot();
  }

  getConfig(): SimConfig {
    return { ...this.config };
  }

  getEconomics(): Economics {
    return { ...this.economics };
  }

  /** @deprecated Prefer ViewModelProjector.setEconomics — kept for callers. */
  setEconomics(next: Partial<Economics>): void {
    this.economics = { ...this.economics, ...next };
  }

  snapOrder(qty: number): number {
    return snapCases(qty, this.config.case_size);
  }

  isConfigDirty(): boolean {
    return !configsEqual(this.config, this.appliedConfig);
  }

  /** Compatibility: accept legacy `{ order_qty }` or a bare number. */
  async stepInput(input: StepInput | number): Promise<DayDelta> {
    const qty = typeof input === "number" ? input : input.order_qty;
    return this.step(qty);
  }

  private applyConfigPartial(next: Partial<SimConfig> & Record<string, unknown>): void {
    this.config = { ...this.config, ...next } as SimConfig;
    if (typeof next.case_size === "number") {
      this.config.case_size = Math.max(1, Math.round(next.case_size));
    }
    this.config.lead_time = 1;
    if (typeof next.seed === "number") {
      this.config.seed = Math.round(next.seed);
    }
  }

  private stepOnce(orderQty: number): DayDelta {
    const drop_oldest = this.state.history.length >= this.config.window_days;
    const { state, dayRecord, completedDay } = stepSimulation(
      this.state,
      orderQty,
      this.config,
    );
    this.state = state;
    this.flatBelief = generateFlatBelief(
      this.state.lots,
      this.state.rng,
      this.config.obs_scenario,
    );
    this.seq += 1;
    return {
      seq: this.seq,
      episode_day: completedDay,
      day: {
        ...dayRecord,
        lots: dayRecord.lots.map((l) => ({ ...l })),
      },
      drop_oldest,
      belief: {
        ...this.flatBelief,
        lot_counts: [...this.flatBelief.lot_counts],
        age_marginals: [...this.flatBelief.age_marginals],
        tau_grid: [...this.flatBelief.tau_grid],
      },
      live_lots: this.state.lots.map((l) => ({ ...l })),
      pipeline: this.pipeline(),
    };
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

  private toSnapshot(): Snapshot {
    return {
      seq: this.seq,
      episode_day: this.state.day,
      belief: {
        ...this.flatBelief,
        lot_counts: [...this.flatBelief.lot_counts],
        age_marginals: [...this.flatBelief.age_marginals],
        tau_grid: [...this.flatBelief.tau_grid],
      },
      history: this.state.history.map((d) => ({
        ...d,
        lots: d.lots.map((l) => ({ ...l })),
      })),
      live_lots: this.state.lots.map((l) => ({ ...l })),
      pipeline: this.pipeline(),
      applied_config: { ...this.appliedConfig },
      schedule: {
        ...MOCK_SCHEDULE,
        delivery_weekdays: [...MOCK_SCHEDULE.delivery_weekdays],
        order_weekdays: [...MOCK_SCHEDULE.order_weekdays],
      },
      demand_summary: {
        ...MOCK_DEMAND_SUMMARY,
        dow_means: [...MOCK_DEMAND_SUMMARY.dow_means],
      },
    };
  }
}

import type { EngineAdapter } from "../engine/adapter";
import type {
  ActOpts,
  DayDelta,
  DemandSummary,
  EngineConfig,
  FlatBelief,
  ScheduleWire,
  Snapshot,
} from "../engine/types";
import type {
  Economics,
  PipelineOrder,
  ScenarioId,
  SimConfig,
  StepInput,
} from "../types";
import {
  DEFAULT_ECONOMICS,
  DEFAULT_SIM_CONFIG,
  createInitialState,
  generateFlatBelief,
  onHandInventory,
  snapCases,
  stepSimulation,
  type SimState,
} from "./generate";

export { generateFlatBelief } from "./generate";

/** Coherent OrderSchedule stubs when live engine is absent (T-085 / ADR 0114). */
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

/**
 * Mock engine speaking Snapshot / DayDelta (EngineAdapter). Presentation
 * (PnL / economics / heatmap) stays in ViewModelProjector.
 */
const EPISODE_HORIZON = 90;

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
      12,
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
      12,
    );
    this.seq = 0;
    return this.toSnapshot();
  }

  async step(order_qty: number): Promise<DayDelta> {
    this.refuseIfEpisodeEnded(1);
    return this.stepOnce(order_qty);
  }

  async step_n(orders: number[]): Promise<DayDelta[]> {
    this.refuseIfEpisodeEnded(orders.length);
    const out: DayDelta[] = [];
    for (const qty of orders) {
      out.push(this.stepOnce(qty));
    }
    return out;
  }

  /**
   * Autopilot act: advance one mock day with a chosen order.
   *
   * Heuristic for `damped_sw` / `rollout` is UI-only — not numeric-parity with
   * Python `rollout_order` / `DampedSurvivalWeightedPolicy` (≠ Python).
   */
  async act(opts?: ActOpts): Promise<DayDelta> {
    this.refuseIfEpisodeEnded(1);
    return this.stepOnce(this.chooseActOrder(opts));
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
      12,
    );
    this.seq = 0;
    return this.toSnapshot();
  }

  async setObsScenario(obs_scenario: string): Promise<Snapshot> {
    this.config = {
      ...this.config,
      obs_scenario: obs_scenario as ScenarioId,
    };
    this.appliedConfig = {
      ...this.appliedConfig,
      obs_scenario: obs_scenario as ScenarioId,
    };
    this.flatBelief = generateFlatBelief(
      this.state.lots,
      this.state.rng,
      this.config.obs_scenario,
      12,
    );
    return this.toSnapshot();
  }

  async set_obs_scenario(obs_scenario: string): Promise<Snapshot> {
    return this.setObsScenario(obs_scenario);
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
        12,
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

  /** Resolve order qty from ActOpts (constant vs UI heuristic). */
  private chooseActOrder(opts?: ActOpts): number {
    const policy = String(opts?.policy ?? "damped_sw");
    const constantQty =
      opts?.order_qty ?? opts?.q ?? opts?.budgets?.order_qty ?? opts?.budgets?.q;

    if (
      policy === "constant" ||
      policy === "const" ||
      policy === "fixed"
    ) {
      return this.snapOrder(typeof constantQty === "number" ? constantQty : 0);
    }

    // UI heuristic for damped_sw / rollout (and aliases): alpha-damped base-stock.
    const alpha = opts?.alpha ?? opts?.budgets?.alpha ?? 0.9;
    const inv = onHandInventory(this.state.lots);
    const pending = this.state.pendingOrders.reduce((s, o) => s + o.qty, 0);
    const gap = Math.max(0, this.config.base_stock - inv - pending);
    return this.snapOrder(gap * alpha);
  }

  private refuseIfEpisodeEnded(nDays: number): void {
    if (nDays <= 0) return;
    const day = this.state.day;
    if (day >= EPISODE_HORIZON || day + nDays > EPISODE_HORIZON) {
      throw new Error(
        `episode ended at day ${EPISODE_HORIZON}; Reset to start a new episode`,
      );
    }
  }

  private stepOnce(orderQty: number): DayDelta {
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
      12,
    );
    this.seq += 1;
    return {
      seq: this.seq,
      episode_day: completedDay,
      day: {
        ...dayRecord,
        lots: dayRecord.lots.map((l) => ({ ...l })),
      },
      drop_oldest: false,
      belief: {
        ...this.flatBelief,
        lot_counts: [...this.flatBelief.lot_counts],
        f_marginals: [...this.flatBelief.f_marginals],
        f_grid: [...this.flatBelief.f_grid],
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
        f_marginals: [...this.flatBelief.f_marginals],
        f_grid: [...this.flatBelief.f_grid],
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

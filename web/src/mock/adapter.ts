import type { EngineAdapter } from "../engine/adapter";
import type {
  ActOpts,
  DayDelta,
  DemandSummary,
  EngineConfig,
  FlatBelief,
  Snapshot,
} from "../engine/types";
import type {
  Economics,
  ObsChannels,
  PipelineOrder,
  ScenarioId,
  SimConfig,
  StepInput,
} from "../types";
import { channelsForPreset, maskFor, maskFromChannels, applyMask } from "../obsMask";
import {
  DEFAULT_ECONOMICS,
  DEFAULT_SIM_CONFIG,
  createInitialState,
  generateFlatBelief,
  mockProtectionTarget,
  onHandInventory,
  snapCases,
  stepSimulation,
  type SimState,
} from "./generate";
import { scheduleFromConfig } from "../calendar/weekCalendar";

export { generateFlatBelief } from "./generate";

/** Chart-ready demand summary stub (~FreshNet scale 30 × DOW factors). */
const MOCK_DEMAND_SUMMARY: DemandSummary = {
  scale_mu: 30,
  dow_means: [29.1228, 30.2511, 27.86433, 25.81527, 27.76173, 33.8766, 35.30814],
};

function configsEqual(a: SimConfig, b: SimConfig): boolean {
  return (Object.keys(a) as (keyof SimConfig)[]).every((k) => {
    if (k === "obs_channels") {
      return JSON.stringify(a.obs_channels) === JSON.stringify(b.obs_channels);
    }
    if (k === "delivery_weekdays") {
      return (
        JSON.stringify(a.delivery_weekdays) === JSON.stringify(b.delivery_weekdays)
      );
    }
    return a[k] === b[k];
  });
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
      obs_channels: channelsForPreset(obs_scenario),
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

  async setObsChannels(channels: ObsChannels): Promise<Snapshot> {
    this.config = {
      ...this.config,
      obs_channels: { ...channels },
    };
    for (const id of ["P0", "P1", "F1", "F1s", "F2a", "F2", "F3"] as ScenarioId[]) {
      const preset = channelsForPreset(id);
      if (
        preset.code_type === channels.code_type &&
        preset.scan_waste === channels.scan_waste &&
        preset.delivery_history === channels.delivery_history
      ) {
        this.config.obs_scenario = id;
        break;
      }
    }
    this.appliedConfig = { ...this.config };
    this.flatBelief = generateFlatBelief(
      this.state.lots,
      this.state.rng,
      this.config.obs_scenario,
      12,
    );
    const belief_history = this.state.history.map((day) => ({
      day: day.day,
      belief: generateFlatBelief(
        this.state.lots,
        this.state.rng,
        this.config.obs_scenario,
        day.day + 1,
      ),
    }));
    return { ...this.toSnapshot(), belief_history };
  }

  async set_obs_channels(channels: ObsChannels): Promise<Snapshot> {
    return this.setObsChannels(channels);
  }

  /**
   * Studio helper: stage knobs on the mock physics. Returns a Snapshot of the
   * current engine fields (no presentation keys) so the projector can patch.
   */
  setConfig(next: Partial<SimConfig>): Snapshot {
    this.applyConfigPartial(next);
    if (next.obs_scenario != null || next.obs_channels != null) {
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

    // UI heuristic for damped_sw / rollout (and aliases): alpha-damped gap to demand cover.
    const alpha = opts?.alpha ?? opts?.budgets?.alpha ?? 0.9;
    const inv = onHandInventory(this.state.lots);
    const pending = this.state.pendingOrders.reduce((s, o) => s + o.qty, 0);
    const target = mockProtectionTarget(this.config);
    const gap = Math.max(0, target - inv - pending);
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
        units: (dayRecord.units ?? []).map((u) => ({ ...u })),
        unit_exits: (dayRecord.unit_exits ?? []).map((e) => ({ ...e })),
      },
      drop_oldest: false,
      belief: {
        ...this.flatBelief,
        lot_counts: [...this.flatBelief.lot_counts],
        f_marginals: [...this.flatBelief.f_marginals],
        f_grid: [...this.flatBelief.f_grid],
      },
      live_lots: this.state.lots.map((l) => ({ ...l })),
      live_units: this.state.units.map((u) => ({ ...u })),
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
        units: (d.units ?? []).map((u) => ({ ...u })),
        unit_exits: (d.unit_exits ?? []).map((e) => ({ ...e })),
      })),
      live_lots: this.state.lots.map((l) => ({ ...l })),
      live_units: this.state.units.map((u) => ({ ...u })),
      pipeline: this.pipeline(),
      applied_config: { ...this.appliedConfig },
      schedule: scheduleFromConfig(this.appliedConfig),
      demand_summary: {
        ...MOCK_DEMAND_SUMMARY,
        dow_means: [...MOCK_DEMAND_SUMMARY.dow_means],
      },
    };
  }

  async tradeoffForecast(): Promise<import("../engine/types").TradeoffForecastResult> {
    const onHand = onHandInventory(this.state.lots);
    const day = this.state.history.length;
    const beliefMass = this.flatBelief.f_marginals.reduce((sum, p) => sum + p, 0);
    const wasteChannelScale =
      this.config.obs_channels?.scan_waste === false
        ? 1.12
        : this.config.obs_channels?.code_type === "gsin"
          ? 0.92
          : 1.0;
    const stateScale = 1 + onHand * 0.02 + day * 0.015 + beliefMass * 0.08;

    const candidates = [0, 8, 16, 24].map((q) => {
      const wasteMean = q * 0.1 * stateScale * wasteChannelScale;
      const missedMean = Math.max(0, 20 - q * 0.2) / stateScale;
      return {
        q,
        waste_mean: wasteMean,
        waste_p10: wasteMean * 0.5,
        waste_p50: wasteMean,
        waste_p90: wasteMean * 1.5,
        missed_mean: missedMean,
        missed_p10: missedMean * 0.5,
        missed_p50: missedMean,
        missed_p90: missedMean * 1.5,
        joint_hist: {
          waste_bins: [0, 2, 4, 8],
          missed_bins: [0, 5, 10, 20],
          counts: [
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1],
          ],
        },
      };
    });
    return { candidates };
  }

  async events(params: {
    since_day: number;
  }): Promise<import("../engine/types").EventsResult> {
    const mask = this.config.obs_channels
      ? maskFromChannels(this.config.obs_channels)
      : maskFor(this.config.obs_scenario);
    const days = this.state.history
      .filter((d) => d.day >= params.since_day)
      .map((d) => {
        const rich = this.richDayFromHistory(d);
        const masked = applyMask(rich, mask);
        return {
          day: d.day,
          arrivals: masked.arrivals,
          sales_total: masked.sales_total ?? null,
          waste_total: masked.waste_total ?? null,
          sales_by: masked.sales_by ?? null,
          waste_by: masked.waste_by ?? null,
          arrivals_by: masked.arrivals_by ?? null,
          lot_ids: masked.lot_ids ?? null,
          arrival_lot_ids: masked.arrival_lot_ids ?? null,
          pack_date_days: masked.pack_date_days ?? null,
          temp_times_d: masked.temp_times_d ?? null,
          temp_temps_c: masked.temp_temps_c ?? null,
          temp_traces_by_lot: masked.temp_traces_by_lot ?? null,
        };
      });
    return { since_day: params.since_day, days };
  }

  private richDayFromHistory(day: import("../types").Day): import("../obsMask").RichObsWire {
    const exits = day.unit_exits ?? [];
    const lotIds = [...new Set(day.lots.map((l) => l.lot_id))].sort(
      (a, b) => a - b,
    );
    const salesBy = lotIds.map(
      (id) =>
        exits.filter((e) => e.lot_id === id && e.cause === "sold").length,
    );
    const wasteBy = lotIds.map(
      (id) =>
        exits.filter((e) => e.lot_id === id && e.cause === "spoiled").length,
    );

    const arrivalMeta = this.arrivalMetaForDay(day);
    const temp = this.tempTraceForDay(day, arrivalMeta.lotIds);

    return {
      day: day.day,
      arrivals: day.arrivals,
      sales_total: day.sales_total,
      waste_total: day.waste_total,
      sales_by: salesBy,
      waste_by: wasteBy,
      lot_ids: lotIds,
      arrival_lot_ids: arrivalMeta.lotIds,
      arrivals_by: arrivalMeta.qtys,
      pack_date_days:
        day.arrivals > 0
          ? Math.max(1, Math.round((1 - (day.f_at_receipt ?? 0.85)) * 14))
          : null,
      temp_times_d: temp.times,
      temp_temps_c: temp.temps,
      temp_traces_by_lot: temp.byLot,
    };
  }

  private arrivalMetaForDay(day: import("../types").Day): {
    lotIds: number[];
    qtys: number[];
  } {
    if (day.arrivals <= 0) return { lotIds: [], qtys: [] };
    const prev = this.state.history.find((h) => h.day === day.day - 1);
    const prevIds = new Set((prev?.lots ?? []).map((l) => l.lot_id));
    const newLots = day.lots.filter((l) => !prevIds.has(l.lot_id));
    if (newLots.length > 0) {
      if (newLots.length === 1) {
        return {
          lotIds: [newLots[0]!.lot_id],
          qtys: [day.arrivals],
        };
      }
      const totalN = newLots.reduce((s, l) => s + l.n, 0) || 1;
      return {
        lotIds: newLots.map((l) => l.lot_id),
        qtys: newLots.map((l) =>
          Math.round((day.arrivals * l.n) / totalN),
        ),
      };
    }
    const newest = day.lots[day.lots.length - 1];
    if (newest) {
      return { lotIds: [newest.lot_id], qtys: [day.arrivals] };
    }
    return { lotIds: [], qtys: [] };
  }

  private tempTraceForDay(
    day: import("../types").Day,
    arrivalLotIds: number[],
  ): {
    times: number[] | null;
    temps: number[] | null;
    byLot: import("../obsMask").TempTraceByLot[] | null;
  } {
    if (day.arrivals <= 0 || arrivalLotIds.length === 0) {
      return { times: null, temps: null, byLot: null };
    }
    const span = 3;
    const times = [0, 1, 2, 3].map((i) => i - span);
    const baseTemp = 2 + (day.day % 5) * 0.3;
    const byLot = arrivalLotIds.map((lotId, i) => ({
      lot_id: lotId,
      times_d: times,
      temps_c: times.map((_, j) => baseTemp + i * 0.4 + j * 0.25),
    }));
    const first = byLot[0]!;
    return {
      times: first.times_d,
      temps: first.temps_c,
      byLot,
    };
  }
}

/**
 * ViewModelProjector — applies Snapshot/DayDelta into the D3 ViewModel;
 * owns economics / PnL / heatmap locally (ADR 0098 / T-054).
 */

import type {
  BeliefGrid,
  BeliefHistoryDay,
  Day,
  Economics,
  Lot,
  PipelineOrder,
  SimConfig,
  Unit,
  ViewModel,
} from "../types";
import {
  DEFAULT_ECONOMICS,
  DEFAULT_SIM_CONFIG,
  computePnL,
  onHandInventory,
} from "../mock/generate";
import { effectiveInventoryFromFlatBelief } from "../charts/inventoryTarget";
import { channelsEqual } from "../obsMask";
import type {
  ArrivalSummary,
  DayDelta,
  DemandSummary,
  FlatBelief,
  ScheduleWire,
  Snapshot,
} from "./types";

export type ProjectorOptions = {
  economics?: Economics;
  window_days?: number;
  config?: SimConfig;
};

/** Heatmap axis labels for belief density (f-native: Freshness × count). */
export function beliefHeatmapAxisLabels(): { x: string; y: string } {
  return { x: "Freshness", y: "Count" };
}

/** Derive missed sales when wire omits stockout (HTTP / Pyodide / WASM). */
export function stockoutFromDayFields(
  demand: number | undefined,
  sales_total: number | undefined,
  explicit?: number | undefined,
): number {
  if (typeof explicit === "number" && Number.isFinite(explicit)) return explicit;
  return Math.max(0, (demand ?? 0) - (sales_total ?? 0));
}

/**
 * Lot×freshness mass matrix: density[l][k] = lot_counts[l] * f_marginals[l*K+k]
 * (ADR 0098 intermediate; presentation rebin is beliefGridFromFlat).
 */
export function densityFromFlatBelief(belief: {
  L: number;
  K: number;
  lot_counts: number[];
  f_marginals: number[];
}): number[][] {
  const { L, K, lot_counts, f_marginals } = belief;
  if (L <= 0) return [];
  const density: number[][] = [];
  for (let l = 0; l < L; l++) {
    const row: number[] = [];
    const count = lot_counts[l] ?? 0;
    for (let k = 0; k < K; k++) {
      row.push(count * (f_marginals[l * K + k] ?? 0));
    }
    density.push(row);
  }
  return density;
}

/** Midpoint edges from bin centers (f_grid → f_edges). */
export function centersToEdges(centers: number[]): number[] {
  if (centers.length === 0) return [];
  if (centers.length === 1) {
    const c = centers[0]!;
    return [c, c + 1];
  }
  const edges: number[] = [
    centers[0]! - (centers[1]! - centers[0]!) / 2,
  ];
  for (let i = 0; i < centers.length - 1; i++) {
    edges.push((centers[i]! + centers[i + 1]!) / 2);
  }
  const last = centers[centers.length - 1]!;
  const prev = centers[centers.length - 2]!;
  edges.push(last + (last - prev) / 2);
  return edges;
}

/**
 * Merged f mass m[k] = Σ_l lot_counts[l] * f_marginals[l*K+k] (T-C2-A / ADR 0130).
 */
export function fMarginalFromFlat(flat: FlatBelief): number[] {
  const { L, K, lot_counts, f_marginals } = flat;
  const m = Array.from({ length: K }, () => 0);
  for (let l = 0; l < L; l++) {
    const count = lot_counts[l] ?? 0;
    for (let k = 0; k < K; k++) {
      m[k]! += count * (f_marginals[l * K + k] ?? 0);
    }
  }
  return m;
}


/** Per-day freshness marginal series for the Primary freshness×time heatmap. */
export type BeliefFreshnessDay = {
  day: number;
  f_edges: number[];
  /** Length K merged freshness mass (Σ_l lot_counts[l] × f_marginals[l,k]). */
  marginal: number[];
};

/** Map rolling belief history → chart-ready freshness marginals per day. */
export function beliefFreshnessSeries(
  beliefHistory: BeliefHistoryDay[],
): BeliefFreshnessDay[] {
  return beliefHistory.map(({ day, flatBelief }) => ({
    day,
    f_edges: centersToEdges(flatBelief.f_grid),
    marginal: fMarginalFromFlat(flatBelief),
  }));
}

function integerCountEdges(maxN: number): number[] {
  const top = Math.max(1, Math.ceil(maxN));
  return Array.from({ length: top + 2 }, (_, i) => i);
}

function countBinFor(edges: number[], n: number): number {
  const rounded = Math.round(n);
  for (let c = 0; c < edges.length - 1; c++) {
    if (rounded >= edges[c]! && rounded < edges[c + 1]!) return c;
  }
  return Math.max(0, edges.length - 2);
}

/**
 * Map flat wire belief → freshness×count BeliefGrid (K×C density; ADR 0109).
 * Optional truthLots extend the count axis to cover truth n.
 */
export function beliefGridFromFlat(
  flat: FlatBelief,
  truthLots?: ReadonlyArray<{ n: number }>,
): BeliefGrid {
  if (flat.L <= 0 || flat.K <= 0) {
    return { density: [], f_edges: [], count_edges: [], f_marginal: [] };
  }

  const { L, K, lot_counts, f_grid, f_marginals } = flat;
  const bin_edges = centersToEdges(f_grid);

  let maxN = 1;
  for (const n of lot_counts) {
    maxN = Math.max(maxN, n);
  }
  if (truthLots) {
    for (const lot of truthLots) {
      maxN = Math.max(maxN, lot.n);
    }
  }
  const count_edges = integerCountEdges(maxN);
  const C = count_edges.length - 1;

  const density: number[][] = Array.from({ length: K }, () =>
    Array.from({ length: C }, () => 0),
  );

  for (let l = 0; l < L; l++) {
    const n_l = lot_counts[l] ?? 0;
    const c = countBinFor(count_edges, n_l);
    for (let k = 0; k < K; k++) {
      density[k]![c]! += n_l * (f_marginals[l * K + k] ?? 0);
    }
  }

  const merged = fMarginalFromFlat(flat);

  return {
    density,
    f_edges: bin_edges,
    freshness_edges: bin_edges,
    count_edges,
    f_marginal: merged,
  };
}

function cloneFlat(belief: FlatBelief): FlatBelief {
  return {
    L: belief.L,
    K: belief.K,
    lot_counts: [...belief.lot_counts],
    f_marginals: [...belief.f_marginals],
    f_grid: [...belief.f_grid],
  };
}

function asDay(
  day: DayDelta["day"],
  liveLotsFallback?: readonly Lot[] | undefined,
  liveUnitsFallback?: readonly Unit[] | undefined,
): Day {
  const d = day as Day;
  const fromDay = d.lots;
  const lotsSrc =
    fromDay != null && fromDay.length > 0
      ? fromDay
      : (liveLotsFallback ?? []);
  const fromUnits = d.units;
  const unitsSrc =
    fromUnits != null && fromUnits.length > 0
      ? fromUnits
      : (liveUnitsFallback ?? []);
  return {
    day: d.day,
    lots: lotsSrc.map((l) => ({ ...l })),
    units: unitsSrc.map((u) => ({ ...u })),
    unit_exits: (d.unit_exits ?? []).map((e) => ({ ...e })),
    sales_total: d.sales_total ?? 0,
    waste_total: d.waste_total ?? 0,
    demand: d.demand ?? 0,
    order_qty: d.order_qty ?? 0,
    arrivals: d.arrivals ?? 0,
    stockout: stockoutFromDayFields(d.demand, d.sales_total, d.stockout),
    f_at_receipt: d.f_at_receipt ?? null,
  };
}

function normalizePipeline(
  pipeline: DayDelta["pipeline"] | Snapshot["pipeline"] | undefined,
  episodeDay: number,
): PipelineOrder[] {
  if (!pipeline) return [];
  return pipeline.map((o) => {
    if ("arrive_on" in o && "days_until" in o) {
      return {
        qty: o.qty,
        arrive_on: o.arrive_on,
        days_until: o.days_until,
      };
    }
    const arrive_on = (o as { arrival_day: number }).arrival_day;
    return {
      qty: o.qty,
      arrive_on,
      days_until: arrive_on - episodeDay,
    };
  });
}

/**
 * Builds the D3 ViewModel from engine payloads. setEconomics must never call an
 * EngineAdapter method (local reproject only).
 */
export class ViewModelProjector {
  private economics: Economics;
  private windowDays: number;
  private config: SimConfig;
  private appliedConfig: SimConfig;
  private episodeDay = 0;
  private history: Day[] = [];
  private beliefHistory: BeliefHistoryDay[] = [];
  private liveLots: Lot[] = [];
  private liveUnits: Unit[] = [];
  private pipeline: PipelineOrder[] = [];
  private flatBelief: FlatBelief = {
    L: 0,
    K: 0,
    lot_counts: [],
    f_marginals: [],
    f_grid: [],
  };
  private demandSummary: DemandSummary | null = null;
  private arrivalSummary: ArrivalSummary | null = null;
  private schedule: ScheduleWire | null = null;
  private viewModel: ViewModel;

  constructor(opts?: ProjectorOptions) {
    this.economics = { ...(opts?.economics ?? DEFAULT_ECONOMICS) };
    this.windowDays = opts?.window_days ?? DEFAULT_SIM_CONFIG.window_days;
    this.config = { ...(opts?.config ?? DEFAULT_SIM_CONFIG) };
    if (opts?.window_days != null) {
      this.config = { ...this.config, window_days: opts.window_days };
    }
    this.appliedConfig = { ...this.config };
    this.viewModel = this.buildViewModel();
  }

  applySnapshot(snapshot: Snapshot): ViewModel {
    this.episodeDay = snapshot.episode_day;
    this.history = (snapshot.history ?? []).map((d) => ({
      ...d,
      lots: d.lots.map((l) => ({ ...l })),
      units: (d.units ?? []).map((u) => ({ ...u })),
      unit_exits: (d.unit_exits ?? []).map((e) => ({ ...e })),
      stockout: stockoutFromDayFields(d.demand, d.sales_total, d.stockout),
    }));
    this.beliefHistory = this.history.map((d) => ({
      day: d.day,
      flatBelief: cloneFlat(snapshot.belief),
    }));
    this.liveLots = (snapshot.live_lots ?? []).map((l) => ({
      ...l,
      f_values: l.f_values ? [...l.f_values] : undefined,
    }));
    this.liveUnits = (snapshot.live_units ?? []).map((u) => ({ ...u }));
    this.pipeline = normalizePipeline(snapshot.pipeline, this.episodeDay);
    this.flatBelief = cloneFlat(snapshot.belief);

    if (snapshot.applied_config) {
      this.config = {
        ...this.config,
        ...snapshot.applied_config,
      } as SimConfig;
      this.appliedConfig = { ...this.config };
      if (typeof snapshot.applied_config.window_days === "number") {
        this.windowDays = snapshot.applied_config.window_days;
      }
    }

    if (snapshot.demand_summary) {
      this.demandSummary = {
        ...snapshot.demand_summary,
        dow_means: [...snapshot.demand_summary.dow_means],
      };
    }
    if (snapshot.arrival_summary) {
      this.arrivalSummary = {
        ...snapshot.arrival_summary,
        curve: snapshot.arrival_summary.curve.map((p) => ({ ...p })),
        baseline_curve: snapshot.arrival_summary.baseline_curve?.map((p) => ({
          ...p,
        })),
      };
    }
    if (snapshot.schedule) {
      this.schedule = {
        ...snapshot.schedule,
        delivery_weekdays: [...snapshot.schedule.delivery_weekdays],
        order_weekdays: [...snapshot.schedule.order_weekdays],
      };
    }

    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  applyDelta(delta: DayDelta): ViewModel {
    this.episodeDay = delta.episode_day;

    const nextDay = asDay(delta.day, delta.live_lots, delta.live_units);
    this.history = [...this.history, nextDay];

    if (delta.belief) {
      this.flatBelief = cloneFlat(delta.belief);
    }
    this.beliefHistory = [
      ...this.beliefHistory,
      { day: nextDay.day, flatBelief: cloneFlat(this.flatBelief) },
    ];
    if (delta.live_lots) {
      this.liveLots = delta.live_lots.map((l) => ({
        ...l,
        f_values: l.f_values ? [...l.f_values] : undefined,
      }));
    }
    if (delta.live_units) {
      this.liveUnits = delta.live_units.map((u) => ({ ...u }));
    }
    if (delta.pipeline) {
      this.pipeline = normalizePipeline(delta.pipeline, this.episodeDay);
    }

    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  setEconomics(economics: Partial<Economics>): ViewModel {
    this.economics = { ...this.economics, ...economics };
    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  setConfig(partial: Partial<SimConfig>): ViewModel {
    this.config = { ...this.config, ...partial };
    if (typeof partial.window_days === "number") {
      this.windowDays = partial.window_days;
    }
    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  patchEngineState(snapshot: Pick<
    Snapshot,
    "belief" | "belief_history" | "live_lots" | "live_units" | "pipeline" | "episode_day" | "applied_config"
  >): ViewModel {
    if (snapshot.episode_day != null) {
      this.episodeDay = snapshot.episode_day;
    }
    if (snapshot.belief_history?.length) {
      for (const entry of snapshot.belief_history) {
        if (entry.belief.L <= 0 || entry.belief.K <= 0) continue;
        const idx = this.beliefHistory.findIndex((b) => b.day === entry.day);
        if (idx >= 0) {
          this.beliefHistory[idx] = {
            day: entry.day,
            flatBelief: cloneFlat(entry.belief),
          };
        }
      }
    }
    if (snapshot.belief) {
      this.flatBelief = cloneFlat(snapshot.belief);
      if (
        snapshot.belief.L > 0 &&
        snapshot.belief.K > 0 &&
        !snapshot.belief_history?.length
      ) {
        const cloned = cloneFlat(this.flatBelief);
        const lastBh = this.beliefHistory[this.beliefHistory.length - 1];
        if (lastBh != null && lastBh.day === this.episodeDay) {
          lastBh.flatBelief = cloned;
        } else if (this.history.length > 0) {
          const lastDay = this.history[this.history.length - 1]!;
          const idx = this.beliefHistory.findIndex((b) => b.day === lastDay.day);
          if (idx >= 0) {
            this.beliefHistory[idx]!.flatBelief = cloned;
          }
        }
      }
    }
    if (snapshot.live_lots) {
      this.liveLots = snapshot.live_lots.map((l) => ({ ...l }));
    }
    if (snapshot.live_units) {
      this.liveUnits = snapshot.live_units.map((u) => ({ ...u }));
    }
    if (snapshot.pipeline) {
      this.pipeline = normalizePipeline(snapshot.pipeline, this.episodeDay);
    }
    if (snapshot.applied_config) {
      this.appliedConfig = {
        ...this.appliedConfig,
        ...snapshot.applied_config,
      } as SimConfig;
      if (snapshot.applied_config.obs_scenario !== undefined) {
        this.config = {
          ...this.config,
          obs_scenario: snapshot.applied_config.obs_scenario,
        };
      }
      if (snapshot.applied_config.obs_channels !== undefined) {
        this.config = {
          ...this.config,
          obs_channels: snapshot.applied_config.obs_channels,
        };
      }
    }
    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  markConfigApplied(): ViewModel {
    this.appliedConfig = { ...this.config };
    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  demandSummaryFromConfig = (partial: {
    demand_mu: number;
    demand_vm: number;
  }): DemandSummary => {
    void partial.demand_vm;
    const base =
      this.demandSummary ??
      ({
        scale_mu: this.config.demand_mu,
        dow_means: Array.from({ length: 7 }, () => this.config.demand_mu),
      } satisfies DemandSummary);
    const scale = partial.demand_mu;
    const factors = base.dow_means.map((m) => m / (base.scale_mu || 1));
    return {
      scale_mu: scale,
      dow_means: factors.map((f) => f * scale),
    };
  };

  getViewModel(): ViewModel {
    return this.viewModel;
  }

  private configsEqual(a: SimConfig, b: SimConfig): boolean {
    return (Object.keys(a) as (keyof SimConfig)[]).every((k) => {
      if (k === "obs_scenario") return true;
      if (k === "obs_channels") {
        return channelsEqual(a.obs_channels, b.obs_channels);
      }
      if (k === "delivery_weekdays") {
        return (
          JSON.stringify(a.delivery_weekdays) === JSON.stringify(b.delivery_weekdays)
        );
      }
      return a[k] === b[k];
    });
  }

  private buildViewModel(): ViewModel {
    const { series, totals } = computePnL(this.history, this.economics);
    const pending = this.pipeline.reduce((s, o) => s + o.qty, 0);
    return {
      episode_day: this.episodeDay,
      window_days: this.windowDays,
      history: this.history.map((d) => ({
        ...d,
        lots: d.lots.map((l) => ({ ...l })),
        units: (d.units ?? []).map((u) => ({ ...u })),
        unit_exits: (d.unit_exits ?? []).map((e) => ({ ...e })),
      })),
      economics: { ...this.economics },
      config: { ...this.config },
      config_dirty: !this.configsEqual(this.config, this.appliedConfig),
      pnl_series: series,
      pnl_totals: totals,
      belief: beliefGridFromFlat(this.flatBelief, this.liveLots),
      live_lots: this.liveLots.map((l) => ({
        ...l,
        f_values: l.f_values ? [...l.f_values] : undefined,
      })),
      live_units: this.liveUnits.map((u) => ({ ...u })),
      belief_history: this.beliefHistory.map((b) => ({
        day: b.day,
        flatBelief: cloneFlat(b.flatBelief),
      })),
      on_hand: onHandInventory(this.liveLots),
      effective_inv: effectiveInventoryFromFlatBelief(this.flatBelief),
      pipeline: this.pipeline.map((o) => ({ ...o })),
      case_size: this.config.case_size,
      pending_order: pending,
      demand_summary: this.demandSummary
        ? {
            ...this.demandSummary,
            dow_means: [...this.demandSummary.dow_means],
          }
        : null,
      arrival_summary: this.arrivalSummary
        ? {
            ...this.arrivalSummary,
            curve: this.arrivalSummary.curve.map((p) => ({ ...p })),
            baseline_curve: this.arrivalSummary.baseline_curve?.map((p) => ({
              ...p,
            })),
          }
        : null,
      schedule: this.schedule
        ? {
            ...this.schedule,
            delivery_weekdays: [...this.schedule.delivery_weekdays],
            order_weekdays: [...this.schedule.order_weekdays],
          }
        : null,
    };
  }
}

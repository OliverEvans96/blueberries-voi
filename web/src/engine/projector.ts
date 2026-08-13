/**
 * ViewModelProjector — applies Snapshot/DayDelta into the D3 ViewModel;
 * owns economics / PnL / ghost / heatmap locally (ADR 0098 / T-054).
 */

import type {
  BeliefGrid,
  Day,
  Economics,
  EpisodeGhost,
  GhostDeltas,
  Lot,
  PipelineOrder,
  SimConfig,
  ViewModel,
} from "../types";
import {
  DEFAULT_ECONOMICS,
  DEFAULT_SIM_CONFIG,
  computePnL,
  onHandInventory,
  survivalWeightedInventory,
} from "../mock/generate";
import type { DayDelta, FlatBelief, Snapshot } from "./types";

export type ProjectorOptions = {
  economics?: Economics;
  window_days?: number;
  config?: SimConfig;
};

/**
 * Lot×age mass matrix: density[l][k] = lot_counts[l] * age_marginals[l*K+k]
 * (ADR 0098 intermediate; presentation rebin is beliefGridFromFlat).
 */
export function densityFromFlatBelief(belief: {
  L: number;
  K: number;
  lot_counts: number[];
  age_marginals: number[];
}): number[][] {
  const { L, K, lot_counts, age_marginals } = belief;
  if (L <= 0) return [];
  const density: number[][] = [];
  for (let l = 0; l < L; l++) {
    const row: number[] = [];
    const count = lot_counts[l] ?? 0;
    for (let k = 0; k < K; k++) {
      row.push(count * (age_marginals[l * K + k] ?? 0));
    }
    density.push(row);
  }
  return density;
}

/** Midpoint edges from bin centers (tau_grid → tau_edges). */
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
 * Merged age mass m[k] = Σ_l lot_counts[l] * age_marginals[l*K+k] (ADR 0109).
 */
export function ageMarginalFromFlat(flat: FlatBelief): number[] {
  const { L, K, lot_counts, age_marginals } = flat;
  const m = Array.from({ length: K }, () => 0);
  for (let l = 0; l < L; l++) {
    const count = lot_counts[l] ?? 0;
    for (let k = 0; k < K; k++) {
      m[k]! += count * (age_marginals[l * K + k] ?? 0);
    }
  }
  return m;
}

function integerCountEdges(maxN: number): number[] {
  const top = Math.max(1, Math.ceil(maxN));
  return Array.from({ length: top + 1 }, (_, i) => i);
}

function countBinFor(edges: number[], n: number): number {
  const rounded = Math.round(n);
  for (let c = 0; c < edges.length - 1; c++) {
    if (rounded >= edges[c]! && rounded < edges[c + 1]!) return c;
  }
  return Math.max(0, edges.length - 2);
}

/**
 * Map flat wire belief → age×count BeliefGrid (K×C density; ADR 0109).
 * Optional truthLots extend the count axis to cover truth n.
 */
export function beliefGridFromFlat(
  flat: FlatBelief,
  truthLots?: ReadonlyArray<{ n: number }>,
): BeliefGrid {
  if (flat.L <= 0 || flat.K <= 0) {
    return { density: [], tau_edges: [], count_edges: [], age_marginal: [] };
  }

  const { L, K, lot_counts, age_marginals, tau_grid } = flat;
  const tau_edges = centersToEdges(tau_grid);

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
      density[k]![c]! += n_l * (age_marginals[l * K + k] ?? 0);
    }
  }

  return {
    density,
    tau_edges,
    count_edges,
    age_marginal: ageMarginalFromFlat(flat),
  };
}

function snapshotGhost(history: Day[], economics: Economics): EpisodeGhost {
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
  economics: Economics,
  ghost: EpisodeGhost | null,
): GhostDeltas | null {
  if (!ghost || ghost.days === 0 || history.length === 0) return null;
  const { series } = computePnL(history, economics);
  const waste = history.reduce((s, d) => s + d.waste_total, 0);
  const stockout = history.reduce((s, d) => s + d.stockout, 0);
  const profit = series.reduce((s, d) => s + d.profit, 0);
  const liveDays = history.length;
  return {
    waste_rate: waste / liveDays - ghost.waste_total / ghost.days,
    stockouts: stockout - ghost.stockout_total,
    profit_cum: profit - ghost.profit_cum,
  };
}

/**
 * Normalize a wire day into the chart Day shape.
 *
 * Python EngineSession (ADR 0100) emits end-of-day cohorts on DayDelta.live_lots
 * and intentionally omits day.lots (minimal chart fields in day_driver). The
 * history / effective-age chart reads history[].lots, so fall back to live_lots
 * when the day payload has no lot snapshot (HTTP / Pyodide). Mock still sends
 * day.lots explicitly and that wins.
 */
function asDay(
  day: DayDelta["day"],
  liveLotsFallback?: readonly Lot[] | undefined,
): Day {
  const d = day as Day;
  const fromDay = d.lots;
  const lotsSrc =
    fromDay != null && fromDay.length > 0
      ? fromDay
      : (liveLotsFallback ?? []);
  return {
    day: d.day,
    lots: lotsSrc.map((l) => ({ ...l })),
    sales_total: d.sales_total ?? 0,
    waste_total: d.waste_total ?? 0,
    demand: d.demand ?? 0,
    order_qty: d.order_qty ?? 0,
    arrivals: d.arrivals ?? 0,
    stockout: d.stockout ?? 0,
    age_at_receipt: d.age_at_receipt ?? null,
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
  private liveLots: Lot[] = [];
  private pipeline: PipelineOrder[] = [];
  private flatBelief: FlatBelief = {
    L: 0,
    K: 0,
    lot_counts: [],
    age_marginals: [],
    tau_grid: [],
  };
  private ghost: EpisodeGhost | null = null;
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
    // Capture ghost from the prior episode when replacing a non-empty window
    // (studio reset path). Init with empty prior history skips this.
    if (this.history.length > 0) {
      this.ghost = snapshotGhost(this.history, this.economics);
    }

    this.episodeDay = snapshot.episode_day;
    this.history = (snapshot.history ?? []).map((d) => ({
      ...d,
      lots: d.lots.map((l) => ({ ...l })),
    }));
    this.liveLots = (snapshot.live_lots ?? []).map((l) => ({ ...l }));
    this.pipeline = normalizePipeline(snapshot.pipeline, this.episodeDay);
    this.flatBelief = {
      ...snapshot.belief,
      lot_counts: [...snapshot.belief.lot_counts],
      age_marginals: [...snapshot.belief.age_marginals],
      tau_grid: [...snapshot.belief.tau_grid],
    };

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

    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  applyDelta(delta: DayDelta): ViewModel {
    this.episodeDay = delta.episode_day;

    if (delta.drop_oldest && this.history.length > 0) {
      this.history = this.history.slice(1);
    }

    this.history = [...this.history, asDay(delta.day, delta.live_lots)];
    // Enforce rolling window even if drop_oldest was omitted.
    if (this.history.length > this.windowDays) {
      this.history = this.history.slice(-this.windowDays);
    }

    if (delta.belief) {
      this.flatBelief = {
        ...delta.belief,
        lot_counts: [...delta.belief.lot_counts],
        age_marginals: [...delta.belief.age_marginals],
        tau_grid: [...delta.belief.tau_grid],
      };
    }
    if (delta.live_lots) {
      this.liveLots = delta.live_lots.map((l) => ({ ...l }));
    }
    if (delta.pipeline) {
      this.pipeline = normalizePipeline(delta.pipeline, this.episodeDay);
    }

    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  /** Local-only: update PnL / ghost from stored history; no engine round-trip. */
  setEconomics(economics: Partial<Economics>): ViewModel {
    this.economics = { ...this.economics, ...economics };
    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  /** Stage sim knobs locally (config dirty until engine reset). */
  setConfig(partial: Partial<SimConfig>): ViewModel {
    this.config = { ...this.config, ...partial };
    if (typeof partial.window_days === "number") {
      this.windowDays = partial.window_days;
    }
    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  /** Refresh belief / lots / pipeline from engine without capturing ghost. */
  patchEngineState(snapshot: Pick<
    Snapshot,
    "belief" | "live_lots" | "pipeline" | "episode_day" | "applied_config"
  >): ViewModel {
    if (snapshot.episode_day != null) {
      this.episodeDay = snapshot.episode_day;
    }
    if (snapshot.belief) {
      this.flatBelief = {
        ...snapshot.belief,
        lot_counts: [...snapshot.belief.lot_counts],
        age_marginals: [...snapshot.belief.age_marginals],
        tau_grid: [...snapshot.belief.tau_grid],
      };
    }
    if (snapshot.live_lots) {
      this.liveLots = snapshot.live_lots.map((l) => ({ ...l }));
    }
    if (snapshot.pipeline) {
      this.pipeline = normalizePipeline(snapshot.pipeline, this.episodeDay);
    }
    if (snapshot.applied_config) {
      this.appliedConfig = {
        ...this.appliedConfig,
        ...snapshot.applied_config,
      } as SimConfig;
    }
    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  markConfigApplied(): ViewModel {
    this.appliedConfig = { ...this.config };
    this.viewModel = this.buildViewModel();
    return this.viewModel;
  }

  /** Current projected ViewModel (after last apply / setEconomics). */
  getViewModel(): ViewModel {
    return this.viewModel;
  }

  private configsEqual(a: SimConfig, b: SimConfig): boolean {
    return (Object.keys(a) as (keyof SimConfig)[]).every((k) => a[k] === b[k]);
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
      })),
      economics: { ...this.economics },
      config: { ...this.config },
      config_dirty: !this.configsEqual(this.config, this.appliedConfig),
      pnl_series: series,
      pnl_totals: totals,
      belief: beliefGridFromFlat(this.flatBelief, this.liveLots),
      live_lots: this.liveLots.map((l) => ({ ...l })),
      on_hand: onHandInventory(this.liveLots),
      effective_inv: survivalWeightedInventory(this.liveLots, this.config),
      pipeline: this.pipeline.map((o) => ({ ...o })),
      ghost: this.ghost,
      ghost_deltas: ghostDeltas(this.history, this.economics, this.ghost),
      case_size: this.config.case_size,
      pending_order: pending,
    };
  }
}

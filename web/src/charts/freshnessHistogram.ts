import * as d3 from "d3";
import { centersToEdges } from "../engine/projector";
import type { FlatBelief } from "../engine/types";
import type { Lot } from "../types";

export type FreshnessHistogramData = {
  /** Freshness bin edges in [0, 1] (length K+1). */
  f_edges: number[];
  /** Bin centers aligned with `belief_masses` (length K). */
  f_centers: number[];
  /** Aggregate belief mass per freshness bin (length K). */
  belief_masses: number[];
  /** Truth lots for overlay (typically `live_lots` when showTruth is on). */
  truth_lots: Lot[];
};

type WeightedSample = { x: number; weight: number };

const KDE_POINTS = 120;

function gaussianKernel(u: number): number {
  return Math.exp(-0.5 * u * u) / Math.sqrt(2 * Math.PI);
}

/** Sum belief mass across all lots for each freshness bin. */
export function aggregateBeliefMasses(flat: FlatBelief): number[] {
  const { L, K, lot_counts, f_marginals } = flat;
  const masses = Array.from({ length: K }, () => 0);
  for (let l = 0; l < L; l++) {
    const count = lot_counts[l] ?? 0;
    for (let k = 0; k < K; k++) {
      masses[k]! += count * (f_marginals[l * K + k] ?? 0);
    }
  }
  return masses;
}

/** Mass-preserving Gaussian KDE on a fixed x grid. */
export function weightedGaussianKde(
  samples: readonly WeightedSample[],
  xGrid: readonly number[],
  bandwidth: number,
): number[] {
  if (bandwidth <= 0 || samples.length === 0) {
    return xGrid.map(() => 0);
  }
  return xGrid.map((x0) => {
    let density = 0;
    for (const { x, weight } of samples) {
      if (weight <= 0) continue;
      density += weight * gaussianKernel((x0 - x) / bandwidth) / bandwidth;
    }
    return density;
  });
}

/** Default bandwidth from average freshness bin width. */
export function defaultBandwidth(f_edges: readonly number[]): number {
  if (f_edges.length < 2) return 0.05;
  const widths = f_edges.slice(1).map((edge, i) => edge - f_edges[i]!);
  const avgWidth = widths.reduce((sum, w) => sum + w, 0) / widths.length;
  return Math.max(avgWidth * 1.5, 0.02);
}

function freshnessXGrid(f_edges: readonly number[]): number[] {
  const lo = f_edges[0] ?? 0;
  const hi = f_edges[f_edges.length - 1] ?? 1;
  return d3.range(lo, hi + (hi - lo) / (KDE_POINTS - 1), (hi - lo) / (KDE_POINTS - 1));
}

/** Aggregate belief KDE (mass ≈ total units). */
export function beliefKdeFromFlat(
  flat: FlatBelief,
  xGrid: readonly number[],
  bandwidth?: number,
): number[] {
  const f_edges = centersToEdges(flat.f_grid);
  const bw = bandwidth ?? defaultBandwidth(f_edges);
  const masses = aggregateBeliefMasses(flat);
  const samples = flat.f_grid.map((x, i) => ({
    x,
    weight: masses[i] ?? 0,
  }));
  return weightedGaussianKde(samples, xGrid, bw);
}

/** Truth KDE from lot means weighted by `n`. */
export function truthKdeFromLots(
  lots: readonly Lot[],
  xGrid: readonly number[],
  f_edges: readonly number[],
  bandwidth?: number,
): number[] {
  const active = lots.filter((lot) => lot.n > 0);
  if (active.length === 0) return xGrid.map(() => 0);
  const bw = bandwidth ?? defaultBandwidth(f_edges);
  const samples = active.map((lot) => ({ x: lot.mean_f, weight: lot.n }));
  return weightedGaussianKde(samples, xGrid, bw);
}

/** Build chart data from flat belief + optional truth lots. */
export function freshnessHistogramDataFromFlat(
  flat: FlatBelief,
  truthLots: readonly Lot[] = [],
): FreshnessHistogramData {
  const f_edges = centersToEdges(flat.f_grid);
  return {
    f_edges,
    f_centers: [...flat.f_grid],
    belief_masses: aggregateBeliefMasses(flat),
    truth_lots: [...truthLots],
  };
}

type KdePoint = { f: number; density: number };

function kdeSeries(xGrid: readonly number[], densities: readonly number[]): KdePoint[] {
  return xGrid.map((f, i) => ({ f, density: densities[i] ?? 0 }));
}

/** Aggregate belief + optional truth KDE overlays (no per-lot separation). */
export function renderFreshnessHistogram(
  container: HTMLElement,
  data: FreshnessHistogramData,
  showTruth: boolean,
  height = 260,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 16, right: 16, bottom: 40, left: 44 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const { f_edges, f_centers, belief_masses, truth_lots } = data;

  container.replaceChildren();
  if (f_edges.length < 2 || f_centers.length === 0) return;

  const xGrid = freshnessXGrid(f_edges);
  const bandwidth = defaultBandwidth(f_edges);
  const beliefSamples = f_centers.map((x, i) => ({
    x,
    weight: belief_masses[i] ?? 0,
  }));
  const beliefDensities = weightedGaussianKde(beliefSamples, xGrid, bandwidth);
  const truthDensities =
    showTruth && truth_lots.length > 0
      ? truthKdeFromLots(truth_lots, xGrid, f_edges, bandwidth)
      : null;

  const yTop =
    Math.max(
      d3.max(beliefDensities) ?? 0,
      truthDensities ? (d3.max(truthDensities) ?? 0) : 0,
      1,
    ) * 1.08;

  const x = d3
    .scaleLinear()
    .domain([f_edges[0]!, f_edges[f_edges.length - 1]!])
    .range([0, innerW]);

  const y = d3.scaleLinear().domain([0, yTop]).nice().range([innerH, 0]);

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Freshness belief and truth KDE with optional truth overlay");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const area = d3
    .area<KdePoint>()
    .x((d) => x(d.f))
    .y0(innerH)
    .y1((d) => y(d.density))
    .curve(d3.curveMonotoneX);

  if (truthDensities) {
    g.append("path")
      .datum(kdeSeries(xGrid, truthDensities))
      .attr("class", "freshness-truth-kde")
      .attr("fill", "var(--color-truth-bar, #1a1a1a)")
      .attr("fill-opacity", 0.2)
      .attr("d", area);
  }

  g.append("path")
    .datum(kdeSeries(xGrid, beliefDensities))
    .attr("class", "freshness-belief-kde")
    .attr("fill", "var(--color-belief-bar, #6b8cae)")
    .attr("fill-opacity", 0.35)
    .attr("d", area);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(5).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 32)
    .attr("text-anchor", "middle")
    .text("Freshness");

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", -innerH / 2)
    .attr("y", -34)
    .attr("transform", "rotate(-90)")
    .attr("text-anchor", "middle")
    .text("Units");

  const legend = svg
    .append("g")
    .attr("class", "legend freshness-histogram-legend")
    .attr("transform", `translate(${margin.left + 4}, 6)`);

  const legendItems: Array<{ label: string; color: string; opacity: number }> = [
    { label: "Belief", color: "var(--color-belief-bar, #6b8cae)", opacity: 0.35 },
  ];
  if (showTruth) {
    legendItems.push({
      label: "Truth",
      color: "var(--color-truth-bar, #1a1a1a)",
      opacity: 0.2,
    });
  }

  legendItems.forEach((item, i) => {
    const itemG = legend
      .append("g")
      .attr("transform", `translate(${i * 72},0)`);
    itemG
      .append("rect")
      .attr("width", 10)
      .attr("height", 10)
      .attr("rx", 2)
      .attr("fill", item.color)
      .attr("fill-opacity", item.opacity);
    itemG
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 14)
      .attr("y", 9)
      .text(item.label);
  });
}

import * as d3 from "d3";
import { centersToEdges } from "../engine/projector";
import type { FlatBelief } from "../engine/types";
import type { Lot, Unit } from "../types";

export const DISPLAY_BIN_COUNT = 8;

export type FreshnessHistogramData = {
  /** Freshness bin edges in [0, 1] (length K+1). */
  f_edges: number[];
  /** Bin centers aligned with `belief_masses` (length K). */
  f_centers: number[];
  /** Aggregate belief mass per freshness bin (length K). */
  belief_masses: number[];
  /** Truth units for overlay (typically `live_units` when showTruth is on). */
  truth_units: Unit[];
};

const BELIEF_COLOR = "#e6b800";
const TRUTH_COLOR = "#2563eb";
const FILL_OPACITY = 0.25;
const TOP_STROKE_WIDTH = 2.5;

type HistBin = {
  index: number;
  x0: number;
  x1: number;
  mass: number;
};

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

/** Build evenly spaced histogram edges over `[lo, hi]`. */
export function histogramEdges(
  lo: number,
  hi: number,
  binCount = DISPLAY_BIN_COUNT,
): number[] {
  return Array.from({ length: binCount + 1 }, (_, i) => lo + (i * (hi - lo)) / binCount);
}

/** Map a freshness value into a histogram bin index. */
export function binIndexForValue(edges: readonly number[], value: number): number {
  const n = edges.length - 1;
  if (n <= 0) return 0;
  if (value <= edges[0]!) return 0;
  if (value >= edges[n]!) return n - 1;
  for (let i = 0; i < n; i++) {
    if (value < edges[i + 1]!) return i;
  }
  return n - 1;
}

/** Rebin source masses (at bin centers) into `targetEdges`. */
export function rebinMasses(
  sourceCenters: readonly number[],
  sourceMasses: readonly number[],
  targetEdges: readonly number[],
): number[] {
  const bins = Array.from({ length: targetEdges.length - 1 }, () => 0);
  for (let i = 0; i < sourceMasses.length; i++) {
    const idx = binIndexForValue(targetEdges, sourceCenters[i] ?? 0);
    bins[idx]! += sourceMasses[i] ?? 0;
  }
  return bins;
}

/** Rebin source masses (over source bin intervals) into `targetEdges`. */
export function rebinMassesByInterval(
  sourceEdges: readonly number[],
  sourceMasses: readonly number[],
  targetEdges: readonly number[],
): number[] {
  const bins = Array.from({ length: targetEdges.length - 1 }, () => 0);
  for (let i = 0; i < sourceMasses.length; i++) {
    const srcLo = sourceEdges[i] ?? 0;
    const srcHi = sourceEdges[i + 1] ?? srcLo;
    const width = srcHi - srcLo;
    if (width <= 0) continue;
    const mass = sourceMasses[i] ?? 0;
    for (let j = 0; j < bins.length; j++) {
      const tgtLo = targetEdges[j] ?? 0;
      const tgtHi = targetEdges[j + 1] ?? tgtLo;
      const overlap = Math.max(0, Math.min(srcHi, tgtHi) - Math.max(srcLo, tgtLo));
      bins[j]! += mass * (overlap / width);
    }
  }
  return bins;
}

/** Aggregate truth lot counts into histogram bins by `mean_f`. */
export function truthMassesInBins(lots: readonly Lot[], edges: readonly number[]): number[] {
  const bins = Array.from({ length: edges.length - 1 }, () => 0);
  for (const lot of lots) {
    if (lot.n <= 0) continue;
    const idx = binIndexForValue(edges, lot.mean_f);
    bins[idx]! += lot.n;
  }
  return bins;
}

/** Count live units into histogram bins by each unit's `f`. */
export function truthMassesFromUnits(
  units: readonly Unit[],
  edges: readonly number[],
): number[] {
  const bins = Array.from({ length: edges.length - 1 }, () => 0);
  for (const unit of units) {
    const idx = binIndexForValue(edges, unit.f);
    bins[idx]! += 1;
  }
  return bins;
}

/** Empty scaffold data — axes/legend only until belief_history arrives. */
export function emptyFreshnessHistogramData(): FreshnessHistogramData {
  const edges = histogramEdges(0, 1, DISPLAY_BIN_COUNT);
  const centers = edges.slice(0, -1).map((lo, i) => (lo + edges[i + 1]!) / 2);
  return {
    f_edges: edges,
    f_centers: centers,
    belief_masses: Array.from({ length: DISPLAY_BIN_COUNT }, () => 0),
    truth_units: [],
  };
}

/** Build chart data from flat belief + optional truth units. */
export function freshnessHistogramDataFromFlat(
  flat: FlatBelief,
  truthUnits: readonly Unit[] = [],
): FreshnessHistogramData {
  const f_edges = centersToEdges(flat.f_grid);
  return {
    f_edges,
    f_centers: [...flat.f_grid],
    belief_masses: aggregateBeliefMasses(flat),
    truth_units: [...truthUnits],
  };
}

function displayBins(
  data: FreshnessHistogramData,
  showTruth: boolean,
): { edges: number[]; belief: number[]; truth: number[] | null } {
  const edges = histogramEdges(0, 1, DISPLAY_BIN_COUNT);
  const belief = rebinMassesByInterval(data.f_edges, data.belief_masses, edges);
  const truth =
    showTruth && data.truth_units.length > 0
      ? truthMassesFromUnits(data.truth_units, edges)
      : null;
  return { edges, belief, truth };
}

/** Aggregate belief + optional truth histogram overlays (~8 bars, no per-lot split). */
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
  const { edges, belief, truth } = displayBins(data, showTruth);

  container.replaceChildren();
  if (edges.length < 2) return;

  const yTop =
    Math.max(
      d3.max(belief) ?? 0,
      truth ? (d3.max(truth) ?? 0) : 0,
      1,
    ) * 1.08;

  const x = d3
    .scaleLinear()
    .domain([edges[0]!, edges[edges.length - 1]!])
    .range([0, innerW]);

  const y = d3.scaleLinear().domain([0, yTop]).nice().range([innerH, 0]);

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Freshness belief and truth histogram with optional truth overlay");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const barGap = 2;
  const toHistBin = (masses: readonly number[]): HistBin[] =>
    masses.map((mass, index) => ({
      index,
      x0: edges[index]!,
      x1: edges[index + 1]!,
      mass,
    }));

  const drawBars = (
    bins: HistBin[],
    fillClass: string,
    capClass: string,
    color: string,
  ): void => {
    const group = g.append("g").attr("class", fillClass.replace("-bar", "-bars"));
    group
      .selectAll("rect")
      .data(bins.filter((b) => b.mass > 0))
      .join("rect")
      .attr("class", fillClass)
      .attr("x", (d) => x(d.x0) + barGap / 2)
      .attr("width", (d) => Math.max(0, x(d.x1) - x(d.x0) - barGap))
      .attr("y", (d) => y(d.mass))
      .attr("height", (d) => Math.max(0, y(0) - y(d.mass)))
      .attr("fill", color)
      .attr("fill-opacity", FILL_OPACITY)
      .append("title")
      .text(
        (d) =>
          `freshness ${d.x0.toFixed(2)}–${d.x1.toFixed(2)}, ${d.mass.toFixed(2)} units`,
      );

    group
      .selectAll("line")
      .data(bins.filter((b) => b.mass > 0))
      .join("line")
      .attr("class", capClass)
      .attr("x1", (d) => x(d.x0) + barGap / 2)
      .attr("x2", (d) => x(d.x1) - barGap / 2)
      .attr("y1", (d) => y(d.mass))
      .attr("y2", (d) => y(d.mass))
      .attr("stroke", color)
      .attr("stroke-width", TOP_STROKE_WIDTH)
      .attr("stroke-linecap", "square");
  };

  if (truth) {
    drawBars(toHistBin(truth), "freshness-truth-bar", "freshness-truth-cap", TRUTH_COLOR);
  }
  drawBars(toHistBin(belief), "freshness-belief-bar", "freshness-belief-cap", BELIEF_COLOR);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(5).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(DISPLAY_BIN_COUNT).tickSizeOuter(0))
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

  const legendItems: Array<{ label: string; color: string }> = [
    { label: "Belief", color: BELIEF_COLOR },
  ];
  if (showTruth) {
    legendItems.push({ label: "Truth", color: TRUTH_COLOR });
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
      .attr("fill-opacity", FILL_OPACITY)
      .attr("stroke", item.color)
      .attr("stroke-width", TOP_STROKE_WIDTH);
    itemG
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 14)
      .attr("y", 9)
      .text(item.label);
  });
}

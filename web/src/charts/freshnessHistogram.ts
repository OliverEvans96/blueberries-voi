import * as d3 from "d3";
import { centersToEdges } from "../engine/projector";
import type { FlatBelief } from "../engine/types";
import type { Lot, Unit } from "../types";
import { BELIEF_BAR_COLOR, TRUTH_BAR_COLOR } from "./beliefFreshnessPalette";

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

const BELIEF_COLOR = BELIEF_BAR_COLOR;
const TRUTH_COLOR = TRUTH_BAR_COLOR;
const BELIEF_FILL_OPACITY = 0.25;
const TRUTH_FILL_OPACITY = 0.35;
const TOP_STROKE_WIDTH = 2.5;
const MEAN_LINE_COLOR = "#000";
const MEAN_LINE_DASH = "5,3";
const MEAN_LINE_WIDTH = 1.5;

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

/** Bin centers (midpoints) for histogram edges. */
export function histogramBinCenters(edges: readonly number[]): number[] {
  return edges.slice(0, -1).map((lo, i) => (lo + edges[i + 1]!) / 2);
}

/** Count-weighted mean freshness from histogram bin masses and centers. */
export function meanFromHistogramMasses(
  centers: readonly number[],
  masses: readonly number[],
): number | null {
  let total = 0;
  let weighted = 0;
  for (let i = 0; i < masses.length; i++) {
    const mass = masses[i] ?? 0;
    total += mass;
    weighted += mass * (centers[i] ?? 0);
  }
  if (total <= 0) {
    return null;
  }
  return weighted / total;
}

/** Mean freshness across live truth units. */
export function truthMeanFromUnits(units: readonly Unit[]): number | null {
  if (units.length <= 0) {
    return null;
  }
  let sum = 0;
  for (const unit of units) {
    sum += unit.f;
  }
  return sum / units.length;
}

/** Unique mean positions for visible belief/truth overlays (rounded for dedup). */
export function freshnessHistogramMeanPositions(
  edges: readonly number[],
  belief: readonly number[],
  truthUnits: readonly Unit[],
  showTruth: boolean,
): number[] {
  const centers = histogramBinCenters(edges);
  const positions: number[] = [];
  const beliefMean = meanFromHistogramMasses(centers, belief);
  if (beliefMean !== null) {
    positions.push(beliefMean);
  }
  if (showTruth && truthUnits.length > 0) {
    const truthMean = truthMeanFromUnits(truthUnits);
    if (truthMean !== null) {
      positions.push(truthMean);
    }
  }
  const seen = new Set<number>();
  const unique: number[] = [];
  for (const value of positions) {
    const key = Math.round(value * 1e6);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(value);
  }
  return unique;
}

/** Rebin histogram chart data onto the standard 8 display bins on [0, 1]. */
export function displayBinMassesFromHistogramData(
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
  const { edges, belief, truth } = displayBinMassesFromHistogramData(data, showTruth);

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
    fillOpacity: number,
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
      .attr("fill-opacity", fillOpacity)
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

  drawBars(toHistBin(belief), "freshness-belief-bar", "freshness-belief-cap", BELIEF_COLOR, BELIEF_FILL_OPACITY);
  if (truth) {
    drawBars(toHistBin(truth), "freshness-truth-bar", "freshness-truth-cap", TRUTH_COLOR, TRUTH_FILL_OPACITY);
  }

  const meanPositions = freshnessHistogramMeanPositions(
    edges,
    belief,
    data.truth_units,
    showTruth,
  );
  if (meanPositions.length > 0) {
    const meanGroup = g.append("g").attr("class", "freshness-mean-lines");
    for (const meanF of meanPositions) {
      meanGroup
        .append("line")
        .attr("class", "freshness-mean-line")
        .attr("x1", x(meanF))
        .attr("x2", x(meanF))
        .attr("y1", 0)
        .attr("y2", innerH)
        .attr("stroke", MEAN_LINE_COLOR)
        .attr("stroke-width", MEAN_LINE_WIDTH)
        .attr("stroke-dasharray", MEAN_LINE_DASH);
    }
  }

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

  type LegendItem =
    | { label: string; kind: "bar"; color: string; fillOpacity: number }
    | { label: string; kind: "mean-line"; color: string };

  const legendItems: LegendItem[] = [
    { label: "Belief", kind: "bar", color: BELIEF_COLOR, fillOpacity: BELIEF_FILL_OPACITY },
  ];
  if (showTruth) {
    legendItems.push({
      label: "Truth",
      kind: "bar",
      color: TRUTH_COLOR,
      fillOpacity: TRUTH_FILL_OPACITY,
    });
  }
  if (meanPositions.length > 0) {
    legendItems.push({ label: "mean", kind: "mean-line", color: MEAN_LINE_COLOR });
  }

  legendItems.forEach((item, i) => {
    const itemG = legend
      .append("g")
      .attr("transform", `translate(${i * 72},0)`);
    if (item.kind === "bar") {
      itemG
        .append("rect")
        .attr("width", 10)
        .attr("height", 10)
        .attr("rx", 2)
        .attr("fill", item.color)
        .attr("fill-opacity", item.fillOpacity)
        .attr("stroke", item.color)
        .attr("stroke-width", TOP_STROKE_WIDTH);
    } else {
      itemG
        .append("line")
        .attr("class", "freshness-mean-legend-swatch")
        .attr("x1", 0)
        .attr("x2", 12)
        .attr("y1", 5)
        .attr("y2", 5)
        .attr("stroke", item.color)
        .attr("stroke-width", MEAN_LINE_WIDTH)
        .attr("stroke-dasharray", MEAN_LINE_DASH);
    }
    itemG
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 14)
      .attr("y", 9)
      .text(item.label);
  });
}

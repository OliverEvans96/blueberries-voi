import * as d3 from "d3";
import { centersToEdges } from "../engine/projector";
import type { FlatBelief } from "../engine/types";
import type { Lot } from "../types";

export type FreshnessLotSegment = {
  /** Belief lot index (0..L-1). */
  lot_index: number;
  /** Truth lot id when known (for legend / highlight). */
  lot_id: number;
  /** Mass per freshness bin (length K). */
  masses: number[];
};

export type FreshnessHistogramData = {
  /** Freshness bin edges in [0, 1] (length K+1). */
  f_edges: number[];
  /** Per-lot belief mass by freshness bin. */
  segments: FreshnessLotSegment[];
  /** Truth lots for overlay (typically `live_lots` when showTruth is on). */
  truth_lots: Lot[];
  /** lot_id of the most recent delivery (stacked underneath, highlight color). */
  highlight_lot_id: number | null;
};

type BinRow = {
  binIndex: number;
  [key: string]: number;
};

const HIGHLIGHT_FILL = "var(--color-freshness-highlight, #c9a227)";
const LOT_COLORS = d3.schemeTableau10;

function lotMassesFromFlat(flat: FlatBelief): number[][] {
  const { L, K, lot_counts, f_marginals } = flat;
  const masses: number[][] = [];
  for (let l = 0; l < L; l++) {
    const row: number[] = [];
    const count = lot_counts[l] ?? 0;
    for (let k = 0; k < K; k++) {
      row.push(count * (f_marginals[l * K + k] ?? 0));
    }
    masses.push(row);
  }
  return masses;
}

function newestLotId(lots: readonly Lot[]): number | null {
  let best: number | null = null;
  for (const lot of lots) {
    if (lot.n <= 0) continue;
    if (best == null || lot.lot_id > best) best = lot.lot_id;
  }
  return best;
}

/** Build chart data from flat belief + optional truth lots for ids / highlight. */
export function freshnessHistogramDataFromFlat(
  flat: FlatBelief,
  truthLots: readonly Lot[] = [],
): FreshnessHistogramData {
  const { L, K, f_grid } = flat;
  const f_edges = centersToEdges(f_grid);
  const masses = lotMassesFromFlat(flat);
  const highlight_lot_id = newestLotId(truthLots);

  const segments: FreshnessLotSegment[] = [];
  for (let l = 0; l < L; l++) {
    const truth = truthLots[l];
    segments.push({
      lot_index: l,
      lot_id: truth?.lot_id ?? l,
      masses: masses[l] ?? Array.from({ length: K }, () => 0),
    });
  }

  return {
    f_edges,
    segments,
    truth_lots: [...truthLots],
    highlight_lot_id,
  };
}

function stackLotKeys(
  segments: FreshnessLotSegment[],
  highlightLotId: number | null,
): string[] {
  const keys = segments.map((s) => `lot_${s.lot_index}`);
  if (highlightLotId == null) return keys;
  const hi = segments.find((s) => s.lot_id === highlightLotId);
  if (!hi) return keys;
  const hiKey = `lot_${hi.lot_index}`;
  return [hiKey, ...keys.filter((k) => k !== hiKey)];
}

function segmentColor(lotId: number, highlightLotId: number | null, index: number): string {
  if (highlightLotId != null && lotId === highlightLotId) return HIGHLIGHT_FILL;
  return LOT_COLORS[index % LOT_COLORS.length]!;
}

/** Stacked freshness histogram with optional truth lot bars. */
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
  const { f_edges, segments, truth_lots, highlight_lot_id } = data;
  const K = f_edges.length - 1;

  container.replaceChildren();
  if (K <= 0 || segments.length === 0) return;

  const rows: BinRow[] = Array.from({ length: K }, (_, binIndex) => {
    const row: BinRow = { binIndex };
    for (const seg of segments) {
      row[`lot_${seg.lot_index}`] = seg.masses[binIndex] ?? 0;
    }
    return row;
  });

  const keys = stackLotKeys(segments, highlight_lot_id);
  const stack = d3.stack<BinRow>().keys(keys).order(d3.stackOrderNone).offset(d3.stackOffsetNone);
  const series = stack(rows);

  const yMax =
    d3.max(rows, (row) =>
      keys.reduce((sum, key) => sum + (Number(row[key]) || 0), 0),
    ) ?? 1;
  const truthMax = showTruth ? (d3.max(truth_lots, (l) => l.n) ?? 0) : 0;
  const yTop = Math.max(yMax, truthMax, 1);

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
    .attr("aria-label", "Stacked freshness histogram with optional truth overlay");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const lotColorByKey = new Map<string, string>();
  segments.forEach((seg, i) => {
    lotColorByKey.set(
      `lot_${seg.lot_index}`,
      segmentColor(seg.lot_id, highlight_lot_id, i),
    );
  });

  g.selectAll(".freshness-stack-series")
    .data(series)
    .join("g")
    .attr("class", (d) => {
      const lotIndex = Number(d.key.replace("lot_", ""));
      const seg = segments.find((s) => s.lot_index === lotIndex);
      const highlight =
        seg && highlight_lot_id != null && seg.lot_id === highlight_lot_id;
      return `freshness-stack-series${highlight ? " freshness-stack-series--highlight" : ""}`;
    })
    .attr("data-lot-key", (d) => d.key)
    .each(function (s) {
      const lotIndex = Number(s.key.replace("lot_", ""));
      const seg = segments.find((item) => item.lot_index === lotIndex);
      d3.select(this)
        .selectAll<SVGRectElement, d3.SeriesPoint<BinRow>>("rect")
        .data(s)
        .join("rect")
        .attr("class", "freshness-stack-segment")
        .attr("x", (d) => x(f_edges[d.data.binIndex]!) + 1)
        .attr("width", (d) =>
          Math.max(
            0,
            x(f_edges[d.data.binIndex + 1]!) - x(f_edges[d.data.binIndex]!) - 2,
          ),
        )
        .attr("y", (d) => y(d[1]))
        .attr("height", (d) => Math.max(0, y(d[0]) - y(d[1])))
        .attr("fill", lotColorByKey.get(s.key) ?? "#888")
        .append("title")
        .text((d) => {
          const mass = d[1] - d[0];
          const f0 = f_edges[d.data.binIndex]!;
          const f1 = f_edges[d.data.binIndex + 1]!;
          return `lot ${seg?.lot_id ?? lotIndex}: freshness ${f0.toFixed(2)}–${f1.toFixed(2)}, ${mass.toFixed(2)} units`;
        });
    });

  if (showTruth && truth_lots.length > 0) {
    const active = truth_lots.filter((l) => l.n > 0);
    const barW = Math.max(3, Math.min(10, innerW / Math.max(active.length * 8, 24)));
    const truthG = g.append("g").attr("class", "truth-overlay");
    truthG
      .selectAll(".truth-bar")
      .data(active)
      .join("rect")
      .attr("class", "truth-bar")
      .attr("x", (d) => x(d.mean_f) - barW / 2)
      .attr("width", barW)
      .attr("y", (d) => y(d.n))
      .attr("height", (d) => Math.max(0, y(0) - y(d.n)))
      .attr("fill", "none")
      .attr("stroke", "var(--color-truth-bar, #1a1a1a)")
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "3 2")
      .attr("opacity", 0.85)
      .append("title")
      .text((d) => `truth lot ${d.lot_id}: f=${d.mean_f.toFixed(2)}, n=${d.n}`);
  }

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

  const legendItems: Array<{ label: string; color: string; cls?: string }> = segments
    .filter((seg) => seg.masses.some((m) => m > 0))
    .map((seg, i) => ({
      label:
        highlight_lot_id != null && seg.lot_id === highlight_lot_id
          ? `Lot ${seg.lot_id} (newest)`
          : `Lot ${seg.lot_id}`,
      color: segmentColor(seg.lot_id, highlight_lot_id, i),
      cls:
        highlight_lot_id != null && seg.lot_id === highlight_lot_id
          ? "freshness-legend--highlight"
          : undefined,
    }));

  if (showTruth) {
    legendItems.push({
      label: "Truth",
      color: "var(--color-truth-bar, #1a1a1a)",
    });
  }

  legendItems.forEach((item, i) => {
    const itemG = legend
      .append("g")
      .attr("class", item.cls ?? "")
      .attr("transform", `translate(${i * 72},0)`);
    itemG
      .append("rect")
      .attr("width", 10)
      .attr("height", 10)
      .attr("rx", 2)
      .attr("fill", item.label === "Truth" ? "none" : item.color)
      .attr("stroke", item.label === "Truth" ? item.color : "none")
      .attr("stroke-width", item.label === "Truth" ? 1.5 : 0)
      .attr("stroke-dasharray", item.label === "Truth" ? "3 2" : null);
    itemG
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 14)
      .attr("y", 9)
      .text(item.label);
  });
}

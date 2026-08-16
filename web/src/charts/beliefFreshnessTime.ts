import * as d3 from "d3";
import {
  beliefFreshnessSeries,
  centersToEdges,
  type BeliefFreshnessDay,
} from "../engine/projector";
import { CHART_MARGIN } from "../hoverLink";
import type { BeliefHistoryDay, Day, HoverDay, Lot } from "../types";

export type BeliefFreshnessTimeDims = {
  width: number;
  height: number;
  margin: { top: number; right: number; bottom: number; left: number };
};

type LotPoint = Lot & { day: number };

/** Sub-day slices between consecutive belief snapshots (visual only). */
export const BELIEF_DAY_SUBSTEPS = 4;
/** Finer freshness bins between belief grid cells (visual only). */
export const BELIEF_F_SUBSTEPS = 4;

export function dayDomain(history: Day[]): [number, number] {
  if (history.length === 0) return [0, 1];
  const days = history.map((d) => d.day);
  return [Math.min(...days), Math.max(...days)];
}

function rootG(
  container: HTMLElement,
): d3.Selection<SVGGElement, unknown, null, undefined> | null {
  const g = container.querySelector("svg g.chart-root");
  return g ? d3.select(g as SVGGElement) : null;
}

/** Style-only hover: classes + one vertical rule. Never rebinds geometry. */
export function setBeliefFreshnessTimeHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void {
  const g = rootG(container);
  if (!g) return;

  g.classed("is-hovering", hoveredDay != null);

  g.selectAll<SVGRectElement, Day>(".day-col").classed(
    "day-col--active",
    (d) => hoveredDay === d.day,
  );

  g.selectAll<SVGCircleElement, LotPoint>(".lot").classed(
    "lot--active",
    (d) => hoveredDay === d.day,
  );

  const rule = g.select<SVGLineElement>(".hover-rule");
  if (hoveredDay == null) {
    rule.attr("opacity", 0);
    return;
  }
  const col = g
    .selectAll<SVGRectElement, Day>(".day-col")
    .filter((d) => d.day === hoveredDay);
  if (col.empty()) {
    rule.attr("opacity", 0);
    return;
  }
  const x = Number(col.attr("x")) + Number(col.attr("width")) / 2;
  rule.attr("x1", x).attr("x2", x).attr("opacity", 1);
}

function fBinCenters(fEdges: number[]): number[] {
  const centers: number[] = [];
  for (let i = 0; i < fEdges.length - 1; i++) {
    centers.push((fEdges[i]! + fEdges[i + 1]!) / 2);
  }
  return centers;
}

function sampleMarginalAtF(
  fEdges: number[],
  marginal: number[],
  f: number,
): number {
  const centers = fBinCenters(fEdges);
  if (centers.length === 0) return 0;
  if (f <= centers[0]!) return marginal[0] ?? 0;
  const last = centers.length - 1;
  if (f >= centers[last]!) return marginal[last] ?? 0;
  for (let i = 0; i < last; i++) {
    const c0 = centers[i]!;
    const c1 = centers[i + 1]!;
    if (f >= c0 && f <= c1) {
      const t = c1 === c0 ? 0 : (f - c0) / (c1 - c0);
      const v0 = marginal[i] ?? 0;
      const v1 = marginal[i + 1] ?? 0;
      return (1 - t) * v0 + t * v1;
    }
  }
  return marginal[last] ?? 0;
}

type HeatCell = { day: number; f0: number; f1: number; value: number };

/** Expand belief snapshots with sub-day and sub-freshness interpolation (display only). */
export function buildBeliefFreshnessHeatmap(
  series: BeliefFreshnessDay[],
  daySubsteps = BELIEF_DAY_SUBSTEPS,
  fSubsteps = BELIEF_F_SUBSTEPS,
): HeatCell[] {
  if (series.length === 0) return [];

  const fEdges = series[0]!.f_edges;
  const fMin = fEdges[0]!;
  const fMax = fEdges[fEdges.length - 1]!;
  const k = fEdges.length - 1;
  const fineK = Math.max(k, (k - 1) * fSubsteps + 1);
  const fineFEdges = Array.from({ length: fineK + 1 }, (_, i) => {
    return fMin + (i / fineK) * (fMax - fMin);
  });

  type Snap = { day: number; marginal: number[]; f_edges: number[] };
  const snaps: Snap[] = [];
  for (let i = 0; i < series.length; i++) {
    const row = series[i]!;
    snaps.push({
      day: row.day,
      marginal: row.marginal,
      f_edges: row.f_edges,
    });
    if (i < series.length - 1) {
      const a = series[i]!;
      const b = series[i + 1]!;
      const span = b.day - a.day || 1;
      for (let s = 1; s < daySubsteps; s++) {
        const t = s / daySubsteps;
        snaps.push({
          day: a.day + t * span,
          marginal: a.marginal.map((v, idx) => (1 - t) * v + t * (b.marginal[idx] ?? 0)),
          f_edges: a.f_edges,
        });
      }
    }
  }

  const cells: HeatCell[] = [];
  for (let si = 0; si < snaps.length; si++) {
    const snap = snaps[si]!;
    const nextDay =
      si < snaps.length - 1 ? snaps[si + 1]!.day : snap.day + 1 / daySubsteps;
    const prevDay = si > 0 ? snaps[si - 1]!.day : snap.day - 1 / daySubsteps;
    const dayHalf = Math.max(
      (nextDay - snap.day) / 2,
      (snap.day - prevDay) / 2,
      0.25 / daySubsteps,
    );

    for (let fi = 0; fi < fineK; fi++) {
      const f0 = fineFEdges[fi]!;
      const f1 = fineFEdges[fi + 1]!;
      const fMid = (f0 + f1) / 2;
      const value = sampleMarginalAtF(snap.f_edges, snap.marginal, fMid);
      cells.push({
        day: snap.day,
        f0,
        f1,
        value,
      });
    }
    void dayHalf;
  }

  return cells;
}

function renderBeliefHeatmapLayer(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  series: BeliefFreshnessDay[],
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerW: number,
): void {
  const cells = buildBeliefFreshnessHeatmap(series);
  if (cells.length === 0) return;

  const maxD = d3.max(cells, (c) => c.value) ?? 1;
  const color = d3
    .scaleSequential(
      d3.interpolateRgbBasis(["#f3efe6", "#9bbf9a", "#2f5d4a", "#17362c"]),
    )
    .domain([0, maxD]);

  const days = [...new Set(cells.map((c) => c.day))].sort((a, b) => a - b);
  const dayHalf =
    days.length > 1
      ? Math.min(
          ...days.slice(1).map((d, i) => (d - days[i]!) / 2),
        )
      : 0.5;

  const heatG = g.append("g").attr("class", "belief-freshness-heatmap");
  heatG
    .selectAll("rect")
    .data(cells)
    .join("rect")
    .attr("class", "belief-freshness-cell")
    .attr("x", (d) => xScale(d.day - dayHalf))
    .attr("width", () =>
      Math.max(1, xScale(dayHalf) - xScale(-dayHalf)),
    )
    .attr("y", (d) => yScale(d.f1))
    .attr("height", (d) => Math.max(0, yScale(d.f0) - yScale(d.f1)))
    .attr("fill", (d) => color(d.value))
    .attr("pointer-events", "none");
  void innerW;
}

function renderLotConnectionLines(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  lotGroups: d3.InternMap<string, LotPoint[]>,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
): void {
  const linesG = g.append("g").attr("class", "lot-connections");
  lotGroups.forEach((points, lotId) => {
    if (points.length < 2) return;
    const sortedPoints = [...points].sort((a, b) => a.day - b.day);
    const line = d3
      .line<LotPoint>()
      .x((d) => xScale(d.day))
      .y((d) => yScale(d.mean_f))
      .curve(d3.curveLinear);
    linesG
      .append("path")
      .datum(sortedPoints)
      .attr("class", "lot-connection")
      .attr("d", line)
      .attr("fill", "none")
      .attr("stroke", "#1f5f86")
      .attr("stroke-width", 1.5)
      .attr("stroke-opacity", 0.6)
      .attr("pointer-events", "none")
      .append("title")
      .text(`Lot ${lotId} trajectory`);
  });
}

/**
 * Freshness × time belief heatmap with optional per-lot truth overlay.
 *
 * @param container - mount node (e.g. `#chart-history` after integrate)
 * @param history - per-day lot snapshots for truth overlay (`history[].lots`)
 * @param beliefHistory - rolling `FlatBelief` per day (`ViewModel.belief_history`)
 * @param showTruth - when false, truth dots/lines are omitted
 */
export function renderBeliefFreshnessTime(
  container: HTMLElement,
  history: Day[],
  beliefHistory: BeliefHistoryDay[],
  showTruth: boolean,
  dims?: Partial<BeliefFreshnessTimeDims>,
): void {
  const width = dims?.width ?? (container.clientWidth || 720);
  const height = dims?.height ?? 220;
  const margin = { ...CHART_MARGIN, ...dims?.margin };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("role", "img")
    .attr("aria-label", "Belief freshness over time with optional truth overlay");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = history.map((d) => d.day);
  const [minDay, maxDay] = dayDomain(history);
  const daySpan = Math.max(1, maxDay - minDay);
  const x = d3
    .scaleLinear()
    .domain([minDay - 0.5, maxDay + 0.5])
    .range([0, innerW]);

  const series = beliefFreshnessSeries(beliefHistory);
  const fEdges =
    series[0]?.f_edges ??
    centersToEdges(beliefHistory[0]?.flatBelief.f_grid ?? [0, 1]);
  const maxF = Math.max(
    1,
    fEdges[fEdges.length - 1] ?? 1,
    d3.max(history, (d) => d3.max(d.lots, (l) => l.mean_f)) ?? 0,
  );
  const y = d3.scaleLinear().domain([0, maxF]).nice().range([innerH, 0]);

  if (series.length > 0) {
    renderBeliefHeatmapLayer(g, series, x, y, innerW);
  }

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(5).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(x)
        .tickValues(days.filter((_, i) => i % 2 === 0 || days.length < 10))
        .tickFormat(d3.format("d"))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", -innerH / 2)
    .attr("y", -34)
    .attr("transform", "rotate(-90)")
    .attr("text-anchor", "middle")
    .text("Freshness f");

  g.append("g")
    .attr("class", "day-cols")
    .selectAll("rect")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", "day-col")
    .attr("data-day", (d) => d.day)
    .attr("x", (d) => x(d.day - 0.5))
    .attr("y", 0)
    .attr("width", (d) => Math.max(1, x(d.day + 0.5) - x(d.day - 0.5)))
    .attr("height", innerH)
    .attr("pointer-events", "none");

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  const truthHistory = showTruth
    ? history
    : history.map((d) => ({ ...d, lots: [] as Lot[] }));

  const maxN =
    d3.max(truthHistory, (d) => d3.max(d.lots, (l) => l.n)) ?? 1;
  const r = d3
    .scaleSqrt()
    .domain([0, maxN])
    .range([3, Math.min(14, (innerW / daySpan) * 0.35)]);

  const points: LotPoint[] = truthHistory.flatMap((d) =>
    d.lots.map((lot) => ({ day: d.day, ...lot })),
  );

  const lotGroups = d3.group(points, (d) => String(d.lot_id));
  if (showTruth && points.length > 0) {
    renderLotConnectionLines(g, lotGroups, x, y);
  }

  g.append("g")
    .attr("class", "lots")
    .attr("pointer-events", "none")
    .selectAll("circle")
    .data(points, (d) => `${(d as LotPoint).day}-${(d as LotPoint).lot_id}`)
    .join(
      (enter) =>
        enter
          .append("circle")
          .attr("class", "lot")
          .attr("data-day", (d) => d.day)
          .attr("cx", (d) => x(d.day))
          .attr("cy", (d) => y(d.mean_f))
          .attr("r", 0)
          .attr("fill", "#1f5f86")
          .attr("fill-opacity", 0.9)
          .attr("stroke", "#0f3f66")
          .attr("stroke-opacity", 0.8)
          .call((s) =>
            s
              .append("title")
              .text(
                (d) =>
                  `Day ${d.day} · lot ${d.lot_id}\nf ${d.mean_f.toFixed(2)} · qty ${d.n}`,
              ),
          )
          .call((s) =>
            s.transition().duration(280).attr("r", (d) => r(d.n)),
          ),
      (update) =>
        update
          .attr("data-day", (d) => d.day)
          .transition()
          .duration(280)
          .attr("cx", (d) => x(d.day))
          .attr("cy", (d) => y(d.mean_f))
          .attr("r", (d) => r(d.n)),
      (exit) => exit.transition().duration(180).attr("r", 0).remove(),
    );
}

import * as d3 from "d3";
import {
  beliefFreshnessSeries,
  type BeliefFreshnessDay,
} from "../engine/projector";
import type { BeliefHistoryDay, Day, HoverDay, Unit, UnitExit } from "../types";
import { pickDayTicks } from "./axisTicks";
import {
  BELIEF_HEATMAP_STOPS,
  TERMINAL_DOT_STROKE,
  TRUTH_OVERLAY_PALETTE,
  TRUTH_TRAJECTORY_STROKE,
  UNIT_TERMINAL_SOLD,
  UNIT_TERMINAL_SPOILED,
} from "./beliefFreshnessPalette";

export {
  TRUTH_TRAJECTORY_STROKE,
  UNIT_TERMINAL_SOLD,
  UNIT_TERMINAL_SPOILED,
} from "./beliefFreshnessPalette";

export type BeliefFreshnessTimeDims = {
  width: number;
  height: number;
  margin: { top: number; right: number; bottom: number; left: number };
};

/** Chart-specific margins (wider than shared stack charts for label + colorbar). */
export const BELIEF_FRESHNESS_TIME_MARGIN = {
  top: 14,
  right: 48,
  bottom: 32,
  left: 48,
} as const;

/** Compact horizontal truth legend band above the plot (added to top margin when shown). */
export const TRUTH_LEGEND_BAND = 13;

const HEATMAP_COLORS = [...BELIEF_HEATMAP_STOPS];
const PLOT_CLIP_ID = "belief-freshness-plot-clip";
const COLORBAR_GRAD_ID = "belief-freshness-colorbar-grad";
const Y_AXIS_LABEL_GUTTER_X = -36;
const TERMINAL_DOT_RADIUS = 1.25;
const TRAJECTORY_STROKE_WIDTH = 0.75;

type UnitPoint = Unit & { day: number };

type TerminalDot = UnitExit & { day: number };

/** Collect per-day unit exits for truth trajectory terminals. */
export function unitTerminalDots(history: readonly Day[]): TerminalDot[] {
  return history.flatMap((d) =>
    (d.unit_exits ?? []).map((exit) => ({ day: d.day, ...exit })),
  );
}

function terminalDotColor(cause: UnitExit["cause"]): string {
  return cause === "spoiled" ? UNIT_TERMINAL_SPOILED : UNIT_TERMINAL_SOLD;
}

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

function heatmapColorScale(maxD: number): d3.ScaleSequential<string> {
  return d3
    .scaleSequential(d3.interpolateRgbBasis(HEATMAP_COLORS))
    .domain([0, maxD]);
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

  g.selectAll<SVGPathElement, [string, UnitPoint[]]>(".unit-trajectory").classed(
    "unit-trajectory--active",
    ([unitId, points]) =>
      points.some((p) => p.day === hoveredDay) ||
      g
        .selectAll<SVGCircleElement, TerminalDot>(
          `.unit-terminal[data-unit-id="${unitId}"]`,
        )
        .filter((d) => d.day === hoveredDay)
        .size() > 0,
  );

  g.selectAll<SVGCircleElement, TerminalDot>(".unit-terminal").classed(
    "unit-terminal--active",
    (d) => d.day === hoveredDay,
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
  const fMin = Math.max(0, fEdges[0]!);
  const fMax = Math.min(1, fEdges[fEdges.length - 1]!);
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

function appendPlotClip(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  innerW: number,
  innerH: number,
): void {
  const defs = g.append("defs");
  defs
    .append("clipPath")
    .attr("id", PLOT_CLIP_ID)
    .append("rect")
    .attr("width", innerW)
    .attr("height", innerH);
}

function renderBeliefHeatmapLayer(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  series: BeliefFreshnessDay[],
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerW: number,
  innerH: number,
): number {
  const cells = buildBeliefFreshnessHeatmap(series);
  if (cells.length === 0) return 1;

  const maxD = d3.max(cells, (c) => c.value) ?? 1;
  const color = heatmapColorScale(maxD);

  const days = [...new Set(cells.map((c) => c.day))].sort((a, b) => a - b);
  const dayHalf =
    days.length > 1
      ? Math.min(...days.slice(1).map((d, i) => (d - days[i]!) / 2))
      : 0.5;

  const heatG = g
    .append("g")
    .attr("class", "belief-freshness-heatmap")
    .attr("clip-path", `url(#${PLOT_CLIP_ID})`);
  heatG
    .selectAll("rect")
    .data(cells)
    .join("rect")
    .attr("class", "belief-freshness-cell")
    .attr("x", (d) => xScale(d.day - dayHalf))
    .attr("width", () => Math.max(1, xScale(dayHalf) - xScale(-dayHalf)))
    .attr("y", (d) => yScale(d.f1))
    .attr("height", (d) => Math.max(0, yScale(d.f0) - yScale(d.f1)))
    .attr("fill", (d) => color(d.value))
    .attr("pointer-events", "none");
  void innerW;
  void innerH;
  return maxD;
}

function renderBeliefFreshnessColorbar(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  innerW: number,
  innerH: number,
  maxD: number,
): void {
  const barX = innerW + 10;
  const barW = 10;
  const defs = g.select<SVGDefsElement>("defs");
  const gradient = defs
    .append("linearGradient")
    .attr("id", COLORBAR_GRAD_ID)
    .attr("x1", "0%")
    .attr("y1", "100%")
    .attr("x2", "0%")
    .attr("y2", "0%");
  const last = HEATMAP_COLORS.length - 1;
  HEATMAP_COLORS.forEach((stopColor, i) => {
    gradient
      .append("stop")
      .attr("offset", `${(i / last) * 100}%`)
      .attr("stop-color", stopColor);
  });

  const cbG = g.append("g").attr("class", "belief-freshness-colorbar");
  cbG
    .append("rect")
    .attr("x", barX)
    .attr("y", 0)
    .attr("width", barW)
    .attr("height", innerH)
    .attr("fill", `url(#${COLORBAR_GRAD_ID})`);

  const scale = d3.scaleLinear().domain([0, maxD]).range([innerH, 0]);
  cbG
    .append("g")
    .attr("class", "axis axis-colorbar")
    .attr("transform", `translate(${barX + barW},0)`)
    .call(
      d3
        .axisRight(scale)
        .ticks(2)
        .tickFormat(d3.format("~s"))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").remove());

  cbG
    .append("text")
    .attr("class", "belief-freshness-colorbar-label axis-label")
    .attr("x", barX + barW / 2)
    .attr("y", -6)
    .attr("text-anchor", "middle")
    .text("Units");
}

function trajectoryPointsForUnit(
  points: UnitPoint[],
  exit: TerminalDot | undefined,
): UnitPoint[] {
  const sorted = [...points].sort((a, b) => a.day - b.day);
  if (exit) {
    sorted.push({
      day: exit.day,
      unit_id: exit.unit_id,
      lot_id: exit.lot_id,
      f: exit.f,
    });
  }
  return sorted;
}

function renderUnitTrajectories(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  unitGroups: d3.InternMap<string, UnitPoint[]>,
  exitsByUnit: Map<string, TerminalDot>,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
): void {
  const trajG = g
    .append("g")
    .attr("class", "unit-trajectories")
    .attr("clip-path", `url(#${PLOT_CLIP_ID})`);
  const line = d3
    .line<UnitPoint>()
    .x((d) => xScale(d.day))
    .y((d) => yScale(d.f))
    .curve(d3.curveLinear);

  trajG
    .selectAll("path")
    .data([...unitGroups.entries()])
    .join("path")
    .attr("class", "unit-trajectory")
    .attr("data-unit-id", ([unitId]) => unitId)
    .attr("d", ([unitId, points]) => {
      const sorted = trajectoryPointsForUnit(points, exitsByUnit.get(unitId));
      return sorted.length >= 2 ? line(sorted) : null;
    })
    .attr("fill", "none")
    .attr("stroke", TRUTH_TRAJECTORY_STROKE)
    .attr("stroke-width", TRAJECTORY_STROKE_WIDTH)
    .attr("stroke-opacity", 0.4)
    .attr("pointer-events", "none")
    .append("title")
    .text(([unitId]) => {
      const exit = exitsByUnit.get(unitId);
      const cause = exit ? ` · ${exit.cause}` : "";
      return `Unit ${unitId}${cause}`;
    });
}

function renderUnitTerminalDots(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  terminals: TerminalDot[],
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
): void {
  if (terminals.length === 0) return;
  const dotsG = g
    .append("g")
    .attr("class", "unit-terminals")
    .attr("clip-path", `url(#${PLOT_CLIP_ID})`);
  dotsG
    .selectAll("circle")
    .data(terminals, (d) => `${(d as TerminalDot).day}-${(d as TerminalDot).unit_id}`)
    .join("circle")
    .attr("class", (d) => `unit-terminal unit-terminal--${d.cause}`)
    .attr("data-day", (d) => d.day)
    .attr("data-unit-id", (d) => d.unit_id)
    .attr("cx", (d) => xScale(d.day))
    .attr("cy", (d) => yScale(d.f))
    .attr("r", TERMINAL_DOT_RADIUS)
    .attr("fill", (d) => terminalDotColor(d.cause))
    .attr("stroke", TERMINAL_DOT_STROKE)
    .attr("stroke-width", 0.5)
    .attr("pointer-events", "none")
    .append("title")
    .text(
      (d) =>
        `Unit ${d.unit_id} · lot ${d.lot_id} · ${d.cause} · f ${d.f.toFixed(2)} · day ${d.day}`,
    );
}

function renderTruthOverlayLegend(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  plotLeft: number,
): void {
  const items: Array<{
    label: string;
    kind: "line" | "dot";
    color: string;
    width: number;
  }> = [
    { label: "Alive", kind: "line", color: TRUTH_OVERLAY_PALETTE.alive, width: 46 },
    { label: "Spoiled", kind: "dot", color: TRUTH_OVERLAY_PALETTE.spoiled, width: 54 },
    { label: "Sold", kind: "dot", color: TRUTH_OVERLAY_PALETTE.sold, width: 40 },
  ];
  const legend = svg
    .append("g")
    .attr("class", "legend belief-freshness-truth-legend")
    .attr("transform", `translate(${plotLeft}, 3)`);

  let x = 0;
  for (const item of items) {
    const row = legend.append("g").attr("transform", `translate(${x}, 0)`);
    if (item.kind === "line") {
      row
        .append("line")
        .attr("x1", 0)
        .attr("x2", 12)
        .attr("y1", 6)
        .attr("y2", 6)
        .attr("stroke", item.color)
        .attr("stroke-width", TRAJECTORY_STROKE_WIDTH)
        .attr("stroke-opacity", 0.65);
    } else {
      row
        .append("circle")
        .attr("cx", 6)
        .attr("cy", 6)
        .attr("r", TERMINAL_DOT_RADIUS)
        .attr("fill", item.color)
        .attr("stroke", TERMINAL_DOT_STROKE)
        .attr("stroke-width", 0.5);
    }
    row
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 14)
      .attr("y", 9)
      .text(item.label);
    x += item.width;
  }
}

/**
 * Freshness × time belief heatmap with optional per-unit truth overlay.
 *
 * @param container - mount node (e.g. `#chart-history` after integrate)
 * @param history - per-day unit snapshots for truth overlay (`history[].units`)
 * @param beliefHistory - rolling `FlatBelief` per day (`ViewModel.belief_history`)
 * @param showTruth - when false, truth trajectories are omitted
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

  const truthHistoryPreview = showTruth
    ? history
    : history.map((d) => ({ ...d, units: [] as Unit[], unit_exits: [] as UnitExit[] }));
  const truthPointCount = truthHistoryPreview.reduce(
    (n, d) => n + (d.units?.length ?? 0),
    0,
  );
  const truthExitCount = truthHistoryPreview.reduce(
    (n, d) => n + (d.unit_exits?.length ?? 0),
    0,
  );
  const showTruthOverlay = showTruth && (truthPointCount > 0 || truthExitCount > 0);
  const legendBand = showTruthOverlay ? TRUTH_LEGEND_BAND : 0;

  const margin = {
    ...BELIEF_FRESHNESS_TIME_MARGIN,
    ...dims?.margin,
    top: (dims?.margin?.top ?? BELIEF_FRESHNESS_TIME_MARGIN.top) + legendBand,
  };
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
    .attr("aria-label", "Belief freshness over time with optional truth overlay")
    .attr("data-margin-left", margin.left)
    .attr("data-margin-right", margin.right)
    .attr("data-margin-top", margin.top)
    .attr("data-margin-bottom", margin.bottom);

  if (showTruthOverlay) {
    renderTruthOverlayLegend(svg, margin.left);
  }

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  appendPlotClip(g, innerW, innerH);

  const days = history.map((d) => d.day);
  const [minDay, maxDay] = dayDomain(history);
  const x = d3
    .scaleLinear()
    .domain([minDay - 0.5, maxDay + 0.5])
    .range([0, innerW]);

  const series = beliefFreshnessSeries(beliefHistory);
  const y = d3.scaleLinear().domain([0, 1]).range([innerH, 0]);

  let heatmapMax = 1;
  if (series.length > 0) {
    heatmapMax = renderBeliefHeatmapLayer(g, series, x, y, innerW, innerH);
    renderBeliefFreshnessColorbar(g, innerW, innerH, heatmapMax);
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
        .tickValues(pickDayTicks(days, innerW))
        .tickFormat(d3.format("d"))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("text")
    .attr("class", "axis-label axis-label-y")
    .attr("text-anchor", "middle")
    .attr("transform", `translate(${Y_AXIS_LABEL_GUTTER_X}, ${innerH / 2}) rotate(-90)`)
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

  const truthHistory = truthHistoryPreview;

  const points: UnitPoint[] = truthHistory.flatMap((d) =>
    (d.units ?? []).map((unit) => ({ day: d.day, ...unit })),
  );
  const terminals = unitTerminalDots(truthHistory);
  const exitsByUnit = new Map(
    terminals.map((exit) => [String(exit.unit_id), exit] as const),
  );

  const unitGroups = d3.group(points, (d) => String(d.unit_id));
  const trajectoryUnits = new Set([
    ...unitGroups.keys(),
    ...exitsByUnit.keys(),
  ]);
  const allUnitGroups = d3.group(
    [...trajectoryUnits].flatMap((unitId) => unitGroups.get(unitId) ?? []),
    (d) => String(d.unit_id),
  );

  if (showTruthOverlay) {
    renderUnitTrajectories(g, allUnitGroups, exitsByUnit, x, y);
  }
  if (showTruth && terminals.length > 0) {
    renderUnitTerminalDots(g, terminals, x, y);
  }
}

import * as d3 from "d3";
import type { Day, HoverDay, Lot, BeliefGrid } from "../types";
import { CHART_MARGIN } from "../hoverLink";

export type HistoryDims = {
  width: number;
  height: number;
  margin: { top: number; right: number; bottom: number; left: number };
};

type LotPoint = Lot & { day: number };

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
export function setHistoryHover(
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

/** Data join only — call on step / resize / new ViewModel, not on hover. */
export function renderHistory(
  container: HTMLElement,
  history: Day[],
  belief?: BeliefGrid,
  truthLots: Lot[] = [],
  dims?: Partial<HistoryDims>,
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
    .attr("aria-label", "Inventory lots by day and freshness");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = history.map((d) => d.day);
  const [minDay, maxDay] = dayDomain(history);
  
  // Sub-day resolution: interpolate between days for smoother transitions
  const daySpan = Math.max(1, maxDay - minDay);
  const subDaySteps = Math.max(daySpan * 2, 20); // 2x interpolation minimum
  const x = d3.scaleLinear()
    .domain([minDay - 0.5, maxDay + 0.5])
    .range([0, innerW]);
  
  const maxF = Math.max(
    1,
    d3.max(history, (d) => d3.max(d.lots, (l) => l.mean_f)) ?? 1,
  );
  const y = d3.scaleLinear().domain([0, maxF]).nice().range([innerH, 0]);

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

  // Render belief heatmap if available
  if (belief && belief.density && belief.density.length > 0) {
    renderBeliefHeatmapBackground(g, belief, x, y, innerW, innerH);
  }
  
  g.append("g")
    .attr("class", "day-cols")
    .selectAll("rect")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", "day-col")
    .attr("data-day", (d) => d.day)
    .attr("x", (d) => x(d.day - 0.5))
    .attr("y", 0)
    .attr("width", x(1) - x(0))
    .attr("height", innerH)
    .attr("pointer-events", "none");

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  const maxN = d3.max(history, (d) => d3.max(d.lots, (l) => l.n)) ?? 1;
  const dayWidth = days.length > 1 ? innerW / daySpan : innerW / 2;
  const r = d3
    .scaleSqrt()
    .domain([0, maxN])
    .range([3, Math.min(14, dayWidth * 0.35)]);

  const color = d3
    .scaleSequential(d3.interpolateRgbBasis(["#7a9e7e", "#2f6b4f", "#1a3d32"]))
    .domain([0, 1]);

  const points: LotPoint[] = history.flatMap((d) =>
    d.lots.map((lot) => ({ day: d.day, ...lot })),
  );

  // Group lots by lot_id for connection lines
  const lotGroups = d3.group(points, (d) => d.lot_id);
  
  // Render lot connection lines (thin lines connecting same lot across days)
  if (truthLots.length > 0) {
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
          .attr("fill", (d) => color(d.mean_f))
          .attr("fill-opacity", 0.88)
          .attr("stroke", "#0f241c")
          .attr("stroke-opacity", 0.18)
          .call((s) =>
            s
              .append("title")
              .text(
                (d) =>
                  `Day ${d.day} · lot ${d.lot_id}\nf ${d.mean_f.toFixed(2)} · qty ${d.n}`,
              ),
          )
          .call((s) =>
            s
              .transition()
              .duration(280)
              .attr("r", (d) => r(d.n)),
          ),
      (update) =>
        update
          .attr("fill", (d) => color(d.mean_f))
          .attr("data-day", (d) => d.day)
          .transition()
          .duration(280)
          .attr("cx", (d) => x(d.day))
          .attr("cy", (d) => y(d.mean_f))
          .attr("r", (d) => r(d.n)),
      (exit) => exit.transition().duration(180).attr("r", 0).remove(),
    );
}

/** Render belief heatmap as background in history chart */
function renderBeliefHeatmapBackground(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  belief: BeliefGrid,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerW: number,
  innerH: number,
): void {
  const fEdges = belief.f_edges ?? belief.freshness_edges ?? [];
  const nF = belief.density.length;
  const nCount = belief.density[0]?.length ?? 0;
  
  if (nF === 0 || nCount === 0 || fEdges.length < 2) return;

  const maxD = d3.max(belief.density, (row) => d3.max(row)) ?? 1;
  const color = d3
    .scaleSequential(d3.interpolateRgbBasis(["transparent", "#9bbf9a55", "#2f5d4a55"]))
    .domain([0, maxD]);

  const heatmapG = g.append("g").attr("class", "belief-heatmap-bg");
  
  for (let fi = 0; fi < nF; fi++) {
    for (let ci = 0; ci < nCount; ci++) {
      const density = belief.density[fi]![ci]!;
      if (density < 0.01) continue; // Skip very low density cells
      
      const f0 = fEdges[fi]!;
      const f1 = fEdges[fi + 1]!;
      const c0 = belief.count_edges[ci]!;
      const c1 = belief.count_edges[ci + 1]!;
      
      // Map count to freshness (assuming belief shows freshness vs count)
      const y0 = yScale(f0);
      const y1 = yScale(f1);
      
      heatmapG
        .append("rect")
        .attr("x", 0)
        .attr("y", Math.min(y0, y1))
        .attr("width", innerW)
        .attr("height", Math.abs(y1 - y0))
        .attr("fill", color(density))
        .attr("opacity", 0.4)
        .attr("pointer-events", "none");
    }
  }
}

/** Render thin lines connecting same lot across days */
function renderLotConnectionLines(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  lotGroups: d3.InternMap<string, LotPoint[]>,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
): void {
  const linesG = g.append("g").attr("class", "lot-connections");
  
  lotGroups.forEach((points, lotId) => {
    if (points.length < 2) return; // Need at least 2 points to draw a line
    
    const sortedPoints = points.sort((a, b) => a.day - b.day);
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

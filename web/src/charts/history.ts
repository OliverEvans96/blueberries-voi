import * as d3 from "d3";
import type { Day, HoverDay, Lot } from "../types";
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
    .attr("aria-label", "Inventory lots by day and age");

  const g = svg
    .append("g")
    .attr("class", "chart-root")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = history.map((d) => d.day);
  const step = days.length > 0 ? innerW / days.length : innerW;
  const maxTau = Math.max(
    10,
    d3.max(history, (d) => d3.max(d.lots, (l) => l.tau)) ?? 10,
  );
  const y = d3.scaleLinear().domain([0, maxTau]).nice().range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(5).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  const xAxis = d3
    .scaleBand<number>()
    .domain(days)
    .range([0, innerW])
    .padding(0);

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(xAxis)
        .tickValues(days.filter((_, i) => i % 2 === 0 || days.length < 10))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", -innerH / 2)
    .attr("y", -34)
    .attr("transform", "rotate(-90)")
    .attr("text-anchor", "middle")
    .text("Effective age (days)");

  // Contiguous day bands (visual + shared x alignment). No pointer handlers —
  // parent linked hover uses day-from-x.
  g.append("g")
    .attr("class", "day-cols")
    .selectAll("rect")
    .data(history, (d) => String((d as Day).day))
    .join("rect")
    .attr("class", "day-col")
    .attr("data-day", (d) => d.day)
    .attr("x", (_, i) => i * step)
    .attr("y", 0)
    .attr("width", step)
    .attr("height", innerH)
    .attr("pointer-events", "none");

  g.append("line")
    .attr("class", "hover-rule")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  const maxN = d3.max(history, (d) => d3.max(d.lots, (l) => l.n)) ?? 1;
  const r = d3
    .scaleSqrt()
    .domain([0, maxN])
    .range([3, Math.min(14, step * 0.35)]);

  const color = d3
    .scaleSequential(d3.interpolateRgbBasis(["#7a9e7e", "#2f6b4f", "#1a3d32"]))
    .domain([0, 10]);

  const points: LotPoint[] = history.flatMap((d) =>
    d.lots.map((lot) => ({ day: d.day, ...lot })),
  );

  const dayIndex = new Map(days.map((d, i) => [d, i]));

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
          .attr("cx", (d) => (dayIndex.get(d.day) ?? 0) * step + step / 2)
          .attr("cy", (d) => y(d.tau))
          .attr("r", 0)
          .attr("fill", (d) => color(d.tau))
          .attr("fill-opacity", 0.88)
          .attr("stroke", "#0f241c")
          .attr("stroke-opacity", 0.18)
          .call((s) =>
            s
              .append("title")
              .text(
                (d) =>
                  `Day ${d.day} · lot ${d.lot_id}\nage ${d.tau} · qty ${d.n}`,
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
          .attr("fill", (d) => color(d.tau))
          .attr("data-day", (d) => d.day)
          .transition()
          .duration(280)
          .attr("cx", (d) => (dayIndex.get(d.day) ?? 0) * step + step / 2)
          .attr("cy", (d) => y(d.tau))
          .attr("r", (d) => r(d.n)),
      (exit) => exit.transition().duration(180).attr("r", 0).remove(),
    );
}

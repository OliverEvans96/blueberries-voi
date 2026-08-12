import * as d3 from "d3";
import type { ChartContext, Day } from "../types";

export type HistoryDims = {
  width: number;
  height: number;
  margin: { top: number; right: number; bottom: number; left: number };
};

const DEFAULT_MARGIN = { top: 12, right: 16, bottom: 28, left: 44 };

export function dayDomain(history: Day[]): [number, number] {
  if (history.length === 0) return [0, 1];
  const days = history.map((d) => d.day);
  return [Math.min(...days), Math.max(...days)];
}

export function renderHistory(
  container: HTMLElement,
  history: Day[],
  ctx: ChartContext,
  dims?: Partial<HistoryDims>,
): void {
  const width = dims?.width ?? (container.clientWidth || 720);
  const height = dims?.height ?? 220;
  const margin = { ...DEFAULT_MARGIN, ...dims?.margin };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("role", "img")
    .attr("aria-label", "Inventory lots by day and age");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const [d0, d1] = dayDomain(history);
  const x = d3.scaleBand<number>().domain(d3.range(d0, d1 + 1)).range([0, innerW]).padding(0.18);
  const y = d3.scaleLinear().domain([0, 10]).range([innerH, 0]);

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
        .tickValues(x.domain().filter((_, i) => i % 2 === 0 || x.domain().length < 10))
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

  // Soft day columns for hover
  g.selectAll(".day-col")
    .data(history)
    .join("rect")
    .attr("class", (d) =>
      ctx.hoveredDay === d.day ? "day-col day-col--active" : "day-col",
    )
    .attr("x", (d) => x(d.day) ?? 0)
    .attr("y", 0)
    .attr("width", x.bandwidth())
    .attr("height", innerH)
    .on("mouseenter", (_, d) => ctx.onHoverDay(d.day))
    .on("mouseleave", () => ctx.onHoverDay(null));

  const maxN = d3.max(history, (d) => d3.max(d.lots, (l) => l.n)) ?? 1;
  const r = d3.scaleSqrt().domain([0, maxN]).range([3, Math.min(14, x.bandwidth() * 0.42)]);

  const color = d3
    .scaleSequential(d3.interpolateRgbBasis(["#7a9e7e", "#2f6b4f", "#1a3d32"]))
    .domain([0, 10]);

  const points = history.flatMap((d) =>
    d.lots.map((lot) => ({ day: d.day, ...lot })),
  );

  g.selectAll(".lot")
    .data(points, (d) => `${(d as { day: number; lot_id: number }).day}-${(d as { lot_id: number }).lot_id}`)
    .join(
      (enter) =>
        enter
          .append("circle")
          .attr("class", "lot")
          .attr("cx", (d) => (x(d.day) ?? 0) + x.bandwidth() / 2)
          .attr("cy", (d) => y(d.tau))
          .attr("r", 0)
          .attr("fill", (d) => color(d.tau))
          .attr("fill-opacity", 0.88)
          .attr("stroke", "#0f241c")
          .attr("stroke-opacity", 0.18)
          .call((s) =>
            s
              .transition()
              .duration(280)
              .attr("r", (d) => r(d.n)),
          ),
      (update) =>
        update
          .attr("fill", (d) => color(d.tau))
          .transition()
          .duration(280)
          .attr("cx", (d) => (x(d.day) ?? 0) + x.bandwidth() / 2)
          .attr("cy", (d) => y(d.tau))
          .attr("r", (d) => r(d.n)),
      (exit) => exit.transition().duration(180).attr("r", 0).remove(),
    )
    .classed("lot--dim", (d) => ctx.hoveredDay != null && ctx.hoveredDay !== d.day)
    .on("mouseenter", (_, d) => ctx.onHoverDay(d.day))
    .on("mouseleave", () => ctx.onHoverDay(null))
    .append("title")
    .text((d) => `Day ${d.day} · lot ${d.lot_id}\nage ${d.tau} · qty ${d.n}`);
}

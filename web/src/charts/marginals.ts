import * as d3 from "d3";
import type { ChartContext, Day } from "../types";
import { dayDomain } from "./history";

type MarginalKind = "sales" | "spoilage";

export function renderMarginal(
  container: HTMLElement,
  history: Day[],
  kind: MarginalKind,
  ctx: ChartContext,
  height = 72,
): void {
  const width = container.clientWidth || 720;
  const margin = { top: 8, right: 16, bottom: kind === "sales" ? 4 : 22, left: 44 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", kind === "sales" ? "Daily sales" : "Daily spoilage");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const [d0, d1] = dayDomain(history);
  const x = d3.scaleBand<number>().domain(d3.range(d0, d1 + 1)).range([0, innerW]).padding(0.18);

  const values = history.map((d) =>
    kind === "sales" ? d.sales_total : d.waste_total,
  );
  const maxV = Math.max(1, d3.max(values) ?? 1);
  const y =
    kind === "sales"
      ? d3.scaleLinear().domain([0, maxV]).range([innerH, 0])
      : d3.scaleLinear().domain([0, maxV]).range([0, innerH]);

  const fill = kind === "sales" ? "var(--sales)" : "var(--spoil)";
  const fillActive = kind === "sales" ? "var(--sales-strong)" : "var(--spoil-strong)";

  g.selectAll(".bar")
    .data(history)
    .join("rect")
    .attr("class", (d) =>
      ctx.hoveredDay === d.day ? "bar bar--active" : "bar",
    )
    .attr("x", (d) => x(d.day) ?? 0)
    .attr("width", x.bandwidth())
    .attr("y", (d) => {
      const v = kind === "sales" ? d.sales_total : d.waste_total;
      return kind === "sales" ? y(v) : 0;
    })
    .attr("height", (d) => {
      const v = kind === "sales" ? d.sales_total : d.waste_total;
      return kind === "sales" ? innerH - y(v) : y(v);
    })
    .attr("fill", (d) => (ctx.hoveredDay === d.day ? fillActive : fill))
    .attr("rx", 2)
    .on("mouseenter", (_, d) => ctx.onHoverDay(d.day))
    .on("mouseleave", () => ctx.onHoverDay(null))
    .append("title")
    .text((d) => {
      const v = kind === "sales" ? d.sales_total : d.waste_total;
      return `Day ${d.day}: ${kind} ${v}`;
    });

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(2).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  if (kind === "spoilage") {
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
  }
}

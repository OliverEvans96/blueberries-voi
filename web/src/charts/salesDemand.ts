import * as d3 from "d3";
import type { Day } from "../types";
import { CHART_MARGIN } from "../hoverLink";

/** Sales vs demand over the rolling window. */
export function renderSalesDemand(
  container: HTMLElement,
  history: Day[],
  height = 130,
): void {
  const width = container.clientWidth || 320;
  const margin = {
    top: 12,
    right: CHART_MARGIN.right,
    bottom: 28,
    left: 40,
  };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  if (history.length === 0) return;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Sales versus demand over days");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = history.map((d) => d.day);
  const step = innerW / days.length;
  const x = (day: number): number => {
    const i = days.indexOf(day);
    return i * step + step / 2;
  };

  const yMax =
    d3.max(history, (d) => Math.max(d.sales_total, d.demand, d.stockout)) ?? 1;
  const y = d3.scaleLinear().domain([0, yMax * 1.1]).nice().range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(3).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(d3.scaleBand<number>().domain(days).range([0, innerW]).padding(0))
        .tickValues(days.filter((_, i) => i % 2 === 0 || days.length < 10))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  // Gap shading where demand > sales (stockout)
  g.selectAll(".gap")
    .data(history.filter((d) => d.demand > d.sales_total))
    .join("rect")
    .attr("class", "sales-demand-gap")
    .attr("x", (d) => x(d.day) - step * 0.35)
    .attr("width", step * 0.7)
    .attr("y", (d) => y(d.demand))
    .attr("height", (d) => Math.max(0, y(d.sales_total) - y(d.demand)));

  const lineSales = d3
    .line<Day>()
    .x((d) => x(d.day))
    .y((d) => y(d.sales_total))
    .curve(d3.curveMonotoneX);
  const lineDemand = d3
    .line<Day>()
    .x((d) => x(d.day))
    .y((d) => y(d.demand))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(history)
    .attr("class", "sd-line sd-demand")
    .attr("fill", "none")
    .attr("d", lineDemand);

  g.append("path")
    .datum(history)
    .attr("class", "sd-line sd-sales")
    .attr("fill", "none")
    .attr("d", lineSales);

  const legend = svg
    .append("g")
    .attr("class", "legend")
    .attr("transform", `translate(${margin.left + 4}, 8)`);
  (
    [
      ["sd-demand", "Demand"],
      ["sd-sales", "Sales"],
    ] as const
  ).forEach(([cls, label], i) => {
    const item = legend.append("g").attr("transform", `translate(${i * 72},0)`);
    item
      .append("line")
      .attr("class", `sd-line ${cls}`)
      .attr("x1", 0)
      .attr("x2", 14)
      .attr("y1", 0)
      .attr("y2", 0);
    item.append("text").attr("class", "legend-label").attr("x", 18).attr("y", 3).text(label);
  });
}

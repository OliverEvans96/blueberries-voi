import * as d3 from "d3";
import { CHART_MARGIN } from "../hoverLink";
import { pickDayTicks } from "./axisTicks";

export type ControllerOrderPoint = {
  day: number;
  order_qty: number;
};

/** Map day history into an order-qty series (mirrors inventorySeries). */
export function controllerOrdersSeries(
  history: ReadonlyArray<{ day: number; order_qty: number }>,
): ControllerOrderPoint[] {
  return history.map((d) => ({ day: d.day, order_qty: d.order_qty }));
}

/** Order quantity over episode days — bar chart. */
export function renderControllerOrders(
  container: HTMLElement,
  history: ReadonlyArray<{ day: number; order_qty: number }>,
  height = 160,
): void {
  const width = container.clientWidth || 320;
  const margin = {
    top: 14,
    right: CHART_MARGIN.right,
    bottom: 28,
    left: 40,
  };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const series = controllerOrdersSeries(history);
  if (series.length === 0) return;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Order quantity over days");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const days = series.map((d) => d.day);
  const x = d3
    .scaleBand<number>()
    .domain(days)
    .range([0, innerW])
    .padding(0.2);

  const yMax = Math.max(d3.max(series, (d) => d.order_qty) ?? 0, 1);
  const y = d3.scaleLinear().domain([0, yMax * 1.08]).nice().range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(x)
        .tickValues(pickDayTicks(days, innerW))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.selectAll<SVGRectElement, ControllerOrderPoint>(".order-bar")
    .data(series)
    .join("rect")
    .attr("class", "order-bar")
    .attr("x", (d) => x(d.day) ?? 0)
    .attr("width", x.bandwidth())
    .attr("y", (d) => y(d.order_qty))
    .attr("height", (d) => Math.max(0, innerH - y(d.order_qty)))
    .attr("fill", "var(--color-order-bar, #4a7c9e)")
    .append("title")
    .text((d) => `Day ${d.day}: order ${d.order_qty}`);
}

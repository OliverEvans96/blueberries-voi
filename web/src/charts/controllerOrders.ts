import * as d3 from "d3";
import { CHART_MARGIN } from "../hoverLink";

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

/** Order quantity over episode days. */
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
  const step = innerW / days.length;
  const x = (day: number): number => {
    const i = days.indexOf(day);
    return i * step + step / 2;
  };

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
        .axisBottom(
          d3.scaleBand<number>().domain(days).range([0, innerW]).padding(0),
        )
        .tickValues(days.filter((_, i) => i % 2 === 0 || days.length < 10))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  const line = d3
    .line<ControllerOrderPoint>()
    .x((d) => x(d.day))
    .y((d) => y(d.order_qty))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(series)
    .attr("class", "order-line")
    .attr("fill", "none")
    .attr("d", line);

  g.selectAll(".order-dot")
    .data(series)
    .join("circle")
    .attr("class", "order-dot")
    .attr("cx", (d) => x(d.day))
    .attr("cy", (d) => y(d.order_qty))
    .attr("r", 2.5)
    .append("title")
    .text((d) => `Day ${d.day}: order ${d.order_qty}`);
}

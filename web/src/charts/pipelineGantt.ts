import * as d3 from "d3";
import type { PipelineOrder, SimConfig } from "../types";

/** Pending order pipeline Gantt: today → arrival within lead-time horizon. */
export function renderPipeline(
  container: HTMLElement,
  pipeline: PipelineOrder[],
  config: SimConfig,
  height = 120,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 10, right: 12, bottom: 28, left: 52 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const horizon = Math.max(config.lead_time, 1, ...pipeline.map((p) => p.days_until));
  const rows = pipeline.length > 0 ? pipeline : [];

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Order pipeline Gantt");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, horizon]).range([0, innerW]);

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(x)
        .ticks(Math.min(horizon + 1, 8))
        .tickFormat((d) => (Number(d) === 0 ? "today" : `+${d}`))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  if (rows.length === 0) {
    g.append("text")
      .attr("class", "axis-label")
      .attr("x", innerW / 2)
      .attr("y", innerH / 2)
      .attr("text-anchor", "middle")
      .text("No pending orders");
    return;
  }

  const y = d3
    .scaleBand<number>()
    .domain(rows.map((_, i) => i))
    .range([0, innerH])
    .padding(0.25);

  const maxQ = d3.max(rows, (d) => d.qty) ?? 1;

  g.selectAll(".pipe-bar")
    .data(rows)
    .join("g")
    .attr("transform", (_, i) => `translate(0,${y(i) ?? 0})`)
    .each(function (d) {
      const gg = d3.select(this);
      const barH = y.bandwidth();
      gg.append("rect")
        .attr("class", "pipe-track")
        .attr("x", 0)
        .attr("width", x(horizon))
        .attr("height", barH)
        .attr("rx", 2);
      gg.append("rect")
        .attr("class", "pipe-bar")
        .attr("x", 0)
        .attr("width", Math.max(2, x(d.days_until)))
        .attr("height", barH)
        .attr("rx", 2)
        .attr("opacity", 0.45 + 0.55 * (d.qty / maxQ));
      gg.append("text")
        .attr("class", "pipe-label")
        .attr("x", -6)
        .attr("y", barH / 2)
        .attr("dy", "0.35em")
        .attr("text-anchor", "end")
        .text(`${d.qty}`);
      gg.append("title").text(
        `${d.qty} units · arrives day ${d.arrive_on} (in ${d.days_until}d) · case ${config.case_size}`,
      );
    });

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 24)
    .attr("text-anchor", "middle")
    .text(`Pipeline · L=${config.lead_time}`);
}

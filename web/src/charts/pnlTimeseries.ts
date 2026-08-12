import * as d3 from "d3";
import type { ChartContext, DayPnL } from "../types";

export function renderPnLTimeseries(
  container: HTMLElement,
  series: DayPnL[],
  ctx: ChartContext,
  height = 140,
): void {
  const width = container.clientWidth || 720;
  const margin = { top: 16, right: 16, bottom: 28, left: 44 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Revenue, cost, and profit over days");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  if (series.length === 0) return;

  const days = series.map((d) => d.day);
  const x = d3
    .scalePoint<number>()
    .domain(days)
    .range([0, innerW])
    .padding(0.4);

  const yExtent = d3.extent(
    series.flatMap((d) => [d.revenue, d.cost_total, d.profit]),
  ) as [number, number];
  const pad = Math.max(2, (yExtent[1] - yExtent[0]) * 0.08);
  const y = d3
    .scaleLinear()
    .domain([yExtent[0] - pad, yExtent[1] + pad])
    .nice()
    .range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-y")
    .call(
      d3
        .axisLeft(y)
        .ticks(4)
        .tickFormat((v) => `$${d3.format(",.0f")(v as number)}`)
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").remove());

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(
      d3
        .axisBottom(x)
        .tickValues(days.filter((_, i) => i % 2 === 0 || days.length < 10))
        .tickSizeOuter(0),
    )
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  // zero line
  if (yExtent[0] < 0 && yExtent[1] > 0) {
    g.append("line")
      .attr("class", "zero-line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", y(0))
      .attr("y2", y(0));
  }

  const line = (key: keyof DayPnL) =>
    d3
      .line<DayPnL>()
      .x((d) => x(d.day) ?? 0)
      .y((d) => y(d[key] as number))
      .curve(d3.curveMonotoneX);

  const seriesSpec: { key: keyof DayPnL; cls: string; label: string }[] = [
    { key: "revenue", cls: "series-revenue", label: "Revenue" },
    { key: "cost_total", cls: "series-cost", label: "Cost" },
    { key: "profit", cls: "series-profit", label: "Profit" },
  ];

  for (const s of seriesSpec) {
    g.append("path")
      .datum(series)
      .attr("class", `pnl-line ${s.cls}`)
      .attr("fill", "none")
      .attr("d", line(s.key));
  }

  // Hover targets + markers
  g.selectAll(".pnl-day")
    .data(series)
    .join("g")
    .attr("class", (d) =>
      ctx.hoveredDay === d.day ? "pnl-day pnl-day--active" : "pnl-day",
    )
    .attr("transform", (d) => `translate(${x(d.day) ?? 0},0)`)
    .each(function (d) {
      const gg = d3.select(this);
      gg.append("line")
        .attr("class", "pnl-guide")
        .attr("y1", 0)
        .attr("y2", innerH)
        .attr("opacity", ctx.hoveredDay === d.day ? 1 : 0);
      for (const s of seriesSpec) {
        gg.append("circle")
          .attr("class", `pnl-dot ${s.cls}`)
          .attr("cy", y(d[s.key] as number))
          .attr("r", ctx.hoveredDay === d.day ? 4.5 : 3);
      }
      gg.append("rect")
        .attr("class", "pnl-hit")
        .attr("x", -10)
        .attr("y", 0)
        .attr("width", 20)
        .attr("height", innerH)
        .on("mouseenter", () => ctx.onHoverDay(d.day))
        .on("mouseleave", () => ctx.onHoverDay(null))
        .append("title")
        .text(
          () =>
            `Day ${d.day}\nRev $${d.revenue.toFixed(0)} · Cost $${d.cost_total.toFixed(0)} · Profit $${d.profit.toFixed(0)}`,
        );
    });

  const legend = svg
    .append("g")
    .attr("class", "legend")
    .attr("transform", `translate(${margin.left + 8}, 10)`);

  seriesSpec.forEach((s, i) => {
    const item = legend.append("g").attr("transform", `translate(${i * 88},0)`);
    item
      .append("line")
      .attr("class", `pnl-line ${s.cls}`)
      .attr("x1", 0)
      .attr("x2", 16)
      .attr("y1", 0)
      .attr("y2", 0);
    item
      .append("text")
      .attr("x", 22)
      .attr("y", 3)
      .attr("class", "legend-label")
      .text(s.label);
  });
}

import * as d3 from "d3";
import type { Lot, SimConfig } from "../types";
import { etaEffective, survivalCurve } from "../mock/generate";

/** Weibull survival S(τ) with lot-age rug sized by n. */
export function renderSurvival(
  container: HTMLElement,
  config: SimConfig,
  lots: Lot[],
  height = 140,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 10, right: 12, bottom: 28, left: 36 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const eta = etaEffective(config);
  const tauMax = Math.max(12, Math.ceil(eta * 1.8), ...(lots.map((l) => l.tau + 2)));
  const curve = survivalCurve(config, tauMax, 80);

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Weibull survival versus age with lot rug");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, tauMax]).range([0, innerW]);
  const y = d3.scaleLinear().domain([0, 1]).range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(5).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickFormat(d3.format(".0%")).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  const line = d3
    .line<(typeof curve)[number]>()
    .x((d) => x(d.tau))
    .y((d) => y(d.s))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(curve)
    .attr("class", "impact-line survival-line")
    .attr("fill", "none")
    .attr("d", line);

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 24)
    .attr("text-anchor", "middle")
    .text(`Age · η_eff ${eta.toFixed(1)}d`);

  const maxN = d3.max(lots, (l) => l.n) ?? 1;
  const r = d3.scaleSqrt().domain([0, maxN]).range([2, 7]);

  g.selectAll(".lot-rug")
    .data(lots)
    .join("circle")
    .attr("class", "lot-rug truth-circle")
    .attr("cx", (d) => x(d.tau))
    .attr("cy", innerH)
    .attr("r", (d) => r(d.n))
    .append("title")
    .text((d) => `lot ${d.lot_id}: age ${d.tau}, n=${d.n}`);
}

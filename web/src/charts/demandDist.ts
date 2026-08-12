import * as d3 from "d3";
import type { SimConfig } from "../types";
import { demandPmf } from "../mock/generate";

/** NB demand pmf with on-hand / effective-inventory coverage markers. */
export function renderDemandDist(
  container: HTMLElement,
  config: SimConfig,
  onHand: number,
  effectiveInv: number,
  height = 140,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 10, right: 12, bottom: 28, left: 36 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const pmf = demandPmf(config);
  const maxK = pmf[pmf.length - 1]?.k ?? 40;
  const maxP = d3.max(pmf, (d) => d.p) ?? 0.01;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Demand distribution with inventory coverage");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, maxK]).range([0, innerW]);
  const y = d3.scaleLinear().domain([0, maxP * 1.1]).range([innerH, 0]);
  const barW = Math.max(1, innerW / (maxK + 1) - 0.5);

  g.selectAll(".pmf-bar")
    .data(pmf)
    .join("rect")
    .attr("class", "pmf-bar")
    .attr("x", (d) => x(d.k))
    .attr("y", (d) => y(d.p))
    .attr("width", barW)
    .attr("height", (d) => innerH - y(d.p));

  // Coverage band: 0 → on-hand (shaded), marker at effective inv
  const coverX = x(Math.min(maxK, onHand));
  g.append("rect")
    .attr("class", "coverage-band")
    .attr("x", 0)
    .attr("y", 0)
    .attr("width", Math.max(0, coverX))
    .attr("height", innerH);

  const mark = (value: number, cls: string, label: string) => {
    const vx = x(Math.min(maxK, Math.max(0, value)));
    g.append("line")
      .attr("class", cls)
      .attr("x1", vx)
      .attr("x2", vx)
      .attr("y1", 0)
      .attr("y2", innerH);
    g.append("text")
      .attr("class", "axis-label")
      .attr("x", vx)
      .attr("y", -1)
      .attr("text-anchor", vx > innerW * 0.7 ? "end" : "start")
      .text(label);
  };

  mark(onHand, "coverage-mark coverage-onhand", `on-hand ${Math.round(onHand)}`);
  mark(
    effectiveInv,
    "coverage-mark coverage-eff",
    `eff ${Math.round(effectiveInv)}`,
  );

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(5).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(3).tickFormat(d3.format(".0%")).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 24)
    .attr("text-anchor", "middle")
    .text(`Demand · μ=${config.demand_mu}, V/M=${config.demand_vm}`);
}

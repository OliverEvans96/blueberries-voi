import * as d3 from "d3";
import type { BeliefGrid } from "../types";

/**
 * Top age-marginal histogram sharing the Belief heatmap tau / age domain
 * (ADR 0109 / T-090).
 */
export function renderBeliefAgeMarginal(
  container: HTMLElement,
  belief: BeliefGrid,
  height = 72,
): void {
  const width = container.clientWidth || 320;
  // Match beliefAgeCount left/right so axes align when stacked.
  const margin = { top: 8, right: 12, bottom: 4, left: 44 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Belief age marginal");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const age_marginal = belief.age_marginal ?? [];
  const { tau_edges } = belief;
  if (age_marginal.length === 0 || tau_edges.length < 2) return;

  const x = d3
    .scaleLinear()
    .domain([tau_edges[0]!, tau_edges[tau_edges.length - 1]!])
    .range([0, innerW]);

  const maxM = d3.max(age_marginal) ?? 1;
  const y = d3.scaleLinear().domain([0, maxM]).range([innerH, 0]);

  for (let k = 0; k < age_marginal.length; k++) {
    const x0 = x(tau_edges[k]!);
    const x1 = x(tau_edges[k + 1]!);
    const v = age_marginal[k]!;
    g.append("rect")
      .attr("x", x0)
      .attr("y", y(v))
      .attr("width", Math.max(0, x1 - x0) - 0.5)
      .attr("height", Math.max(0, innerH - y(v)))
      .attr("fill", "#2f5d4a")
      .attr("opacity", 0.85)
      .append("title")
      .text(
        `age ${tau_edges[k]!.toFixed(1)}–${tau_edges[k + 1]!.toFixed(1)}: ${v.toFixed(2)}`,
      );
  }

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(2).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());
}

import * as d3 from "d3";
import type { BeliefGrid } from "../types";

function freshnessEdges(belief: BeliefGrid): number[] {
  return belief.f_edges ?? belief.freshness_edges ?? belief.tau_edges;
}

function isFreshnessGrid(belief: BeliefGrid): boolean {
  return belief.f_edges != null || belief.freshness_edges != null;
}

/**
 * Top f / age marginal histogram sharing the belief heatmap x domain
 * (ADR 0109 / T-090; f-native freshness in [0, 1] per ADR 0130).
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
  const freshness = isFreshnessGrid(belief);
  const xEdges = freshnessEdges(belief);

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr(
      "aria-label",
      freshness ? "Belief freshness marginal" : "Belief age marginal",
    );

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const age_marginal = belief.age_marginal ?? [];
  if (age_marginal.length === 0 || xEdges.length < 2) return;

  const x = d3
    .scaleLinear()
    .domain([xEdges[0]!, xEdges[xEdges.length - 1]!])
    .range([0, innerW]);

  const maxM = d3.max(age_marginal) ?? 1;
  const y = d3.scaleLinear().domain([0, maxM]).range([innerH, 0]);

  for (let k = 0; k < age_marginal.length; k++) {
    const x0 = x(xEdges[k]!);
    const x1 = x(xEdges[k + 1]!);
    const v = age_marginal[k]!;
    const xLabel = freshness ? "freshness" : "age";
    const fmt = (n: number) => (freshness ? n.toFixed(2) : n.toFixed(1));
    g.append("rect")
      .attr("x", x0)
      .attr("y", y(v))
      .attr("width", Math.max(0, x1 - x0) - 0.5)
      .attr("height", Math.max(0, innerH - y(v)))
      .attr("fill", "#2f5d4a")
      .attr("opacity", 0.85)
      .append("title")
      .text(`${xLabel} ${fmt(xEdges[k]!)}–${fmt(xEdges[k + 1]!)}: ${v.toFixed(2)}`);
  }

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(2).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());
}

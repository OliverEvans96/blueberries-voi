import * as d3 from "d3";
import type { Day, SimConfig } from "../types";
import { arrivalAgePriorPdf, f2aPriorPdf } from "../mock/generate";

function recentReceiptAges(history: Day[]): number[] {
  return history
    .filter((d) => d.age_at_receipt != null && d.arrivals > 0)
    .map((d) => d.age_at_receipt as number);
}

/** Arrival-age prior PDF + optional rug of recent age_at_receipt samples. */
export function renderArrivalPrior(
  container: HTMLElement,
  config: SimConfig,
  history: Day[],
  height = 160,
  showReceiptRug = true,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 12, right: 12, bottom: 28, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const prior = arrivalAgePriorPdf(config);
  const f2a = f2aPriorPdf(config);
  const samples = recentReceiptAges(history);
  const yMax =
    Math.max(
      d3.max(prior, (d) => d.density) ?? 0.1,
      d3.max(f2a, (d) => d.density) ?? 0.1,
    ) * 1.15;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Arrival age prior with recent receipt ages");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, 12]).range([0, innerW]);
  const y = d3.scaleLinear().domain([0, yMax]).range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  const area = d3
    .area<(typeof prior)[number]>()
    .x((d) => x(d.tau))
    .y0(innerH)
    .y1((d) => y(d.density))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(prior)
    .attr("fill", "var(--accent, #3d6b5a)")
    .attr("fill-opacity", 0.22)
    .attr("d", area);

  const line = d3
    .line<(typeof prior)[number]>()
    .x((d) => x(d.tau))
    .y((d) => y(d.density))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(prior)
    .attr("class", "impact-line")
    .attr("fill", "none")
    .attr("stroke", "var(--accent, #3d6b5a)")
    .attr("stroke-width", 1.6)
    .attr("d", line);

  g.append("path")
    .datum(f2a)
    .attr("fill", "none")
    .attr("stroke", "var(--muted, #8a7a5c)")
    .attr("stroke-width", 1.2)
    .attr("stroke-dasharray", "4 3")
    .attr("d", line);

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 24)
    .attr("text-anchor", "middle")
    .text("Age at receipt (eff. days)");

  g.selectAll(".arrival-rug")
    .data(showReceiptRug ? samples : [])
    .join("line")
    .attr("class", "arrival-rug truth-cross")
    .attr("x1", (d) => x(d))
    .attr("x2", (d) => x(d))
    .attr("y1", innerH)
    .attr("y2", innerH - 10)
    .attr("stroke", "var(--ink, #1e1a14)")
    .attr("stroke-opacity", 0.55)
    .attr("stroke-width", 1.5)
    .append("title")
    .text((d) => `age_at_receipt ${d.toFixed(2)}`);
}

/** How transit temperature bias shifts the arrival prior (MOD-18 teaching). */
export function renderArrivalShift(
  container: HTMLElement,
  config: SimConfig,
  height = 150,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 12, right: 12, bottom: 28, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const baseline = arrivalAgePriorPdf(config, { transitBiasOverride: 0 });
  const shifted = arrivalAgePriorPdf(config);
  const yMax =
    Math.max(
      d3.max(baseline, (d) => d.density) ?? 0.1,
      d3.max(shifted, (d) => d.density) ?? 0.1,
    ) * 1.15;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr(
      "aria-label",
      "Arrival prior at zero transit bias versus current bias",
    );

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, 12]).range([0, innerW]);
  const y = d3.scaleLinear().domain([0, yMax]).range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  const line = d3
    .line<(typeof baseline)[number]>()
    .x((d) => x(d.tau))
    .y((d) => y(d.density))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(baseline)
    .attr("fill", "none")
    .attr("stroke", "var(--muted, #8a7a5c)")
    .attr("stroke-width", 1.4)
    .attr("stroke-dasharray", "5 3")
    .attr("d", line);

  g.append("path")
    .datum(shifted)
    .attr("class", "impact-line")
    .attr("fill", "none")
    .attr("stroke", "var(--accent, #3d6b5a)")
    .attr("stroke-width", 1.8)
    .attr("d", line);

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 24)
    .attr("text-anchor", "middle")
    .text(
      `Transit bias ${config.transit_temp_bias_c >= 0 ? "+" : ""}${config.transit_temp_bias_c.toFixed(1)}°C · dashed = 0`,
    );
}

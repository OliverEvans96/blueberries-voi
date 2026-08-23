import * as d3 from "d3";
import type { ArrivalSummary } from "../engine/types";
import type { Day } from "../types";

function recentReceiptFreshness(history: Day[]): number[] {
  return history
    .filter((d) => d.f_at_receipt != null && d.arrivals > 0)
    .map((d) => d.f_at_receipt as number);
}

type DensityPoint = { f: number; density: number };

/** Arrival-freshness prior PDF from engine snapshot + optional rug of recent f_at_receipt. */
export function renderArrivalPrior(
  container: HTMLElement,
  arrivalSummary: ArrivalSummary | null,
  history: Day[],
  height = 160,
  showReceiptRug = true,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 12, right: 12, bottom: 28, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const prior: DensityPoint[] = arrivalSummary?.curve ?? [];
  const samples = recentReceiptFreshness(history);
  const yMax =
    (prior.length > 0 ? (d3.max(prior, (d) => d.density) ?? 0.1) : 0.1) * 1.15;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Arrival freshness prior with recent receipt samples");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, 1]).range([0, innerW]);
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

  if (prior.length > 0) {
    const area = d3
      .area<DensityPoint>()
      .x((d) => x(d.f))
      .y0(innerH)
      .y1((d) => y(d.density))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(prior)
      .attr("fill", "var(--accent, #3d6b5a)")
      .attr("fill-opacity", 0.22)
      .attr("d", area);

    const line = d3
      .line<DensityPoint>()
      .x((d) => x(d.f))
      .y((d) => y(d.density))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(prior)
      .attr("class", "impact-line")
      .attr("fill", "none")
      .attr("stroke", "var(--accent, #3d6b5a)")
      .attr("stroke-width", 1.6)
      .attr("d", line);
  }

  if (arrivalSummary && arrivalSummary.f_zero > 1e-6) {
    g.append("text")
      .attr("class", "axis-label")
      .attr("x", x(0.02))
      .attr("y", 10)
      .attr("text-anchor", "start")
      .attr("fill", "var(--muted, #8a7a5c)")
      .text(`P(f=0) ${(arrivalSummary.f_zero * 100).toFixed(1)}%`);
  }

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 24)
    .attr("text-anchor", "middle")
    .text("Freshness at receipt (f)");

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
    .text((d) => `f_at_receipt ${d.toFixed(3)}`);
}

/** How transit temperature bias shifts the engine arrival prior (MOD-18 teaching). */
export function renderArrivalShift(
  container: HTMLElement,
  arrivalSummary: ArrivalSummary | null,
  transitBiasC: number,
  height = 150,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 12, right: 12, bottom: 28, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const shifted: DensityPoint[] = arrivalSummary?.curve ?? [];
  const baseline: DensityPoint[] =
    arrivalSummary?.baseline_curve ?? shifted;
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

  const x = d3.scaleLinear().domain([0, 1]).range([0, innerW]);
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
    .line<DensityPoint>()
    .x((d) => x(d.f))
    .y((d) => y(d.density))
    .curve(d3.curveMonotoneX);

  if (baseline.length > 0) {
    g.append("path")
      .datum(baseline)
      .attr("fill", "none")
      .attr("stroke", "var(--muted, #8a7a5c)")
      .attr("stroke-width", 1.4)
      .attr("stroke-dasharray", "5 3")
      .attr("d", line);
  }

  if (shifted.length > 0) {
    g.append("path")
      .datum(shifted)
      .attr("class", "impact-line")
      .attr("fill", "none")
      .attr("stroke", "var(--accent, #3d6b5a)")
      .attr("stroke-width", 1.8)
      .attr("d", line);
  }

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 24)
    .attr("text-anchor", "middle")
    .text(
      `Transit bias ${transitBiasC >= 0 ? "+" : ""}${transitBiasC.toFixed(1)}°C · dashed = 0`,
    );
}

import * as d3 from "d3";
import { etaEffective, storeTempFactor } from "../mock/generate";
import type { SimConfig } from "../types";

/** Gamma aging defaults (ModelParams / voi_core). */
export const GAMMA_SHAPE = 2.0;

/** θ from reference life: k·θ·η_ref = 1 (production `set_reference_life`). */
export function gammaScale(cfg: SimConfig): number {
  return 1 / (GAMMA_SHAPE * cfg.eta_ref);
}

/** Q10 aging-rate multiplier at store temperature T (°C). */
export function q10RateAtTemp(
  q10: number,
  tRefC: number,
  tempC: number,
): number {
  return Math.max(1.01, q10) ** ((tempC - tRefC) / 10);
}

/** Relative aging rate vs temperature for teaching chart. */
export function arrheniusCurve(
  cfg: SimConfig,
  steps = 40,
): { tempC: number; rate: number }[] {
  const tMin = cfg.t_ref_c - 8;
  const tMax = cfg.t_ref_c + 12;
  const pts: { tempC: number; rate: number }[] = [];
  for (let i = 0; i <= steps; i += 1) {
    const tempC = tMin + ((tMax - tMin) * i) / steps;
    pts.push({
      tempC,
      rate: q10RateAtTemp(cfg.q10, cfg.t_ref_c, tempC),
    });
  }
  return pts;
}

/** Shape-scaled gamma decrement stats at store temperature (ADR 0144 parity). */
export function gammaDecrementStats(cfg: SimConfig): {
  shape: number;
  theta: number;
  phi: number;
  meanDelta: number;
} {
  const theta = gammaScale(cfg);
  const phi = storeTempFactor(cfg);
  const shape = GAMMA_SHAPE * phi;
  return {
    shape,
    theta,
    phi,
    meanDelta: shape * theta,
  };
}

export type FreshnessEnvelopePoint = {
  day: number;
  mean: number;
  std: number;
  lower: number;
  upper: number;
};

/** Uncensored sum-of-Gammas mean ± 1σ envelope until expected expiry. */
export function gammaFreshnessEnvelope(
  cfg: SimConfig,
  opts?: { startF?: number },
): FreshnessEnvelopePoint[] {
  const startF = opts?.startF ?? 1;
  const { meanDelta, shape, theta } = gammaDecrementStats(cfg);
  if (meanDelta <= 0) return [{ day: 0, mean: startF, std: 0, lower: startF, upper: startF }];

  const spoilDay = expectedSpoilDay(cfg, startF);
  const rows: FreshnessEnvelopePoint[] = [];
  for (let day = 0; day <= spoilDay; day += 1) {
    const mean = startF - day * meanDelta;
    const std = day === 0 ? 0 : theta * Math.sqrt(day * shape);
    rows.push({
      day,
      mean,
      std,
      lower: Math.max(0, mean - std),
      upper: Math.min(1, mean + std),
    });
  }
  return rows;
}

/** Day when uncensored mean freshness reaches zero. */
export function expectedSpoilDay(cfg: SimConfig, startF = 1): number {
  const { meanDelta } = gammaDecrementStats(cfg);
  if (meanDelta <= 0) return 0;
  return Math.ceil(startF / meanDelta);
}

/** Q10 / Arrhenius-style aging rate vs store temperature. */
export function renderArrheniusTemp(
  container: HTMLElement,
  config: SimConfig,
  height = 160,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 12, right: 12, bottom: 40, left: 44 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const curve = arrheniusCurve(config);
  const storeRate = storeTempFactor(config);
  const etaEff = etaEffective(config);
  const yMax = Math.max(d3.max(curve, (d) => d.rate) ?? 1, storeRate) * 1.12;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", "Q10 aging rate versus store temperature");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3
    .scaleLinear()
    .domain(d3.extent(curve, (d) => d.tempC) as [number, number])
    .range([0, innerW]);
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

  g.append("line")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("y1", y(1))
    .attr("y2", y(1))
    .attr("stroke", "var(--muted, #8a7a5c)")
    .attr("stroke-dasharray", "4 3")
    .attr("stroke-opacity", 0.7);

  const line = d3
    .line<(typeof curve)[number]>()
    .x((d) => x(d.tempC))
    .y((d) => y(d.rate))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(curve)
    .attr("class", "impact-line")
    .attr("fill", "none")
    .attr("stroke", "var(--accent, #3d6b5a)")
    .attr("stroke-width", 1.8)
    .attr("d", line);

  g.append("circle")
    .attr("cx", x(config.t_ref_c))
    .attr("cy", y(1))
    .attr("r", 4)
    .attr("fill", "var(--muted, #8a7a5c)");

  g.append("circle")
    .attr("cx", x(config.t_store_c))
    .attr("cy", y(storeRate))
    .attr("r", 5)
    .attr("fill", "var(--accent, #3d6b5a)");

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 24)
    .attr("text-anchor", "middle")
    .text(
      `Q10 aging rate · store ${config.t_store_c.toFixed(0)}°C vs T_ref ${config.t_ref_c.toFixed(0)}°C · η_eff ${etaEff.toFixed(1)} d`,
    );
}

/** Gamma decrement mean ± 1σ freshness envelope until expected expiry. */
export function renderGammaFreshnessPath(
  container: HTMLElement,
  config: SimConfig,
  height = 170,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 12, right: 12, bottom: 28, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const envelope = gammaFreshnessEnvelope(config);
  const spoilDay = expectedSpoilDay(config);
  const { shape, theta } = gammaDecrementStats(config);
  const xMax = Math.max(spoilDay, 1);

  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr(
      "aria-label",
      "Unit freshness mean and one standard deviation envelope until expected expiry",
    );

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, xMax]).range([0, innerW]);
  const y = d3.scaleLinear().domain([0, 1]).range([innerH, 0]);

  g.append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(Math.min(6, xMax + 1)).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(5).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  const band = d3
    .area<FreshnessEnvelopePoint>()
    .x((d) => x(d.day))
    .y0((d) => y(d.lower))
    .y1((d) => y(d.upper))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(envelope)
    .attr("class", "gamma-std-band")
    .attr("fill", "var(--accent, #3d6b5a)")
    .attr("fill-opacity", 0.18)
    .attr("d", band);

  const meanLine = d3
    .line<FreshnessEnvelopePoint>()
    .x((d) => x(d.day))
    .y((d) => y(Math.max(0, d.mean)))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(envelope)
    .attr("class", "impact-line")
    .attr("fill", "none")
    .attr("stroke", "var(--accent, #3d6b5a)")
    .attr("stroke-width", 1.8)
    .attr("d", meanLine);

  if (spoilDay > 0) {
    g.append("line")
      .attr("class", "gamma-expiry-mark")
      .attr("x1", x(spoilDay))
      .attr("x2", x(spoilDay))
      .attr("y1", innerH)
      .attr("y2", y(0))
      .attr("stroke", "var(--ink, #1e1a14)")
      .attr("stroke-opacity", 0.35)
      .attr("stroke-dasharray", "3 3");
  }

  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 24)
    .attr("text-anchor", "middle")
    .text(
      `γ(${shape.toFixed(2)}, ${theta.toFixed(4)}) mean ± σ · expiry day ${spoilDay}`,
    );
}

import * as d3 from "d3";
import type { SimConfig } from "../types";
import {
  ARRIVAL_PREVIEW_DEFAULTS,
  durationPmfForProduct,
  expectedDurationDays,
  lambdaBreakDelta,
  lambdaClean,
  phiBreak,
  phiSetForThermalMode,
  phiSetFromLegs,
  poissonPmf,
} from "../arrivalModelPreview";

type LotteryBar = { label: string; pmf: number; lambda: number; highlight?: boolean };

function renderDualAxisLottery(
  container: HTMLElement,
  title: string,
  bars: LotteryBar[],
  xLabel: string,
  pmfLabel: string,
  lambdaLabel: string,
  height = 168,
): void {
  const width = container.clientWidth || 320;
  const margin = { top: 28, right: 48, bottom: 32, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  const svg = d3
    .select(container)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr("aria-label", title);

  svg
    .append("text")
    .attr("x", margin.left)
    .attr("y", 16)
    .attr("class", "impact-caption")
    .text(title);

  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);
  const x = d3
    .scaleBand<string>()
    .domain(bars.map((b) => b.label))
    .range([0, innerW])
    .padding(0.2);
  const yPmf = d3
    .scaleLinear()
    .domain([0, (d3.max(bars, (b) => b.pmf) ?? 0.1) * 1.15])
    .range([innerH, 0]);
  const yLambda = d3
    .scaleLinear()
    .domain([0, (d3.max(bars, (b) => b.lambda) ?? 1) * 1.1])
    .range([innerH, 0]);

  g.selectAll("rect.bar")
    .data(bars)
    .join("rect")
    .attr("class", "bar")
    .attr("x", (d) => x(d.label) ?? 0)
    .attr("y", (d) => yPmf(d.pmf))
    .attr("width", x.bandwidth())
    .attr("height", (d) => innerH - yPmf(d.pmf))
    .attr("fill", (d) => (d.highlight ? "#1d4ed8" : "#6366f1"))
    .attr("opacity", 0.85);

  const line = d3
    .line<LotteryBar>()
    .x((d) => (x(d.label) ?? 0) + x.bandwidth() / 2)
    .y((d) => yLambda(d.lambda));

  g.append("path")
    .datum(bars)
    .attr("fill", "none")
    .attr("stroke", "#f97316")
    .attr("stroke-width", 2)
    .attr("d", line);

  g.selectAll("circle.lambda")
    .data(bars)
    .join("circle")
    .attr("class", "lambda")
    .attr("cx", (d) => (x(d.label) ?? 0) + x.bandwidth() / 2)
    .attr("cy", (d) => yLambda(d.lambda))
    .attr("r", 4)
    .attr("fill", "#f97316");

  g.append("g")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  g.append("g")
    .call(d3.axisLeft(yPmf).ticks(4).tickFormat(d3.format(".2f")))
    .append("text")
    .attr("fill", "currentColor")
    .attr("x", -innerH / 2)
    .attr("y", -32)
    .attr("transform", "rotate(-90)")
    .attr("text-anchor", "middle")
    .text(pmfLabel);

  g.append("g")
    .attr("transform", `translate(${innerW},0)`)
    .call(d3.axisRight(yLambda).ticks(4).tickFormat(d3.format(".1f")))
    .append("text")
    .attr("fill", "#f97316")
    .attr("x", innerH / 2)
    .attr("y", -innerW - 36)
    .attr("transform", "rotate(90)")
    .attr("text-anchor", "middle")
    .text(lambdaLabel);

  g.append("text")
    .attr("x", innerW / 2)
    .attr("y", innerH + 28)
    .attr("text-anchor", "middle")
    .attr("class", "axis-label")
    .text(xLabel);
}

export function renderDurationLottery(
  container: HTMLElement,
  config: Pick<SimConfig, "arrival_product" | "transit_temp_bias_c">,
  height = 168,
): void {
  const pmf = durationPmfForProduct(config.arrival_product);
  const phiSet = phiSetFromLegs(config.transit_temp_bias_c);
  const meanD = expectedDurationDays(config.arrival_product);
  const bars: LotteryBar[] = ARRIVAL_PREVIEW_DEFAULTS.integerDays.map((k) => ({
    label: String(k),
    pmf: pmf[k] ?? 0,
    lambda: lambdaClean(k, phiSet),
    highlight: Math.abs(k - Math.round(meanD)) < 0.5,
  }));
  renderDualAxisLottery(
    container,
    `Duration lottery · ${config.arrival_product} (clean chain)`,
    bars,
    "transit days d",
    "P(d)",
    "Λ (ref-days)",
    height,
  );
}

export function renderBreakLottery(
  container: HTMLElement,
  config: Pick<SimConfig, "break_rho" | "arrival_product" | "transit_temp_bias_c">,
  height = 168,
): void {
  const dBar = expectedDurationDays(config.arrival_product);
  const phiSet = phiSetFromLegs(config.transit_temp_bias_c);
  const phiBrk = phiBreak();
  const mu = config.break_rho * dBar;
  const pmf = poissonPmf(mu, 4);
  const bars: LotteryBar[] = pmf.map((p, n) => ({
    label: String(n),
    pmf: p,
    lambda: lambdaBreakDelta(n, ARRIVAL_PREVIEW_DEFAULTS.tauBar, phiSet, phiBrk),
    highlight: n === 0,
  }));
  renderDualAxisLottery(
    container,
    `Break lottery · ρ=${config.break_rho.toFixed(2)}/d on d̄=${dBar.toFixed(1)} d`,
    bars,
    "break count N",
    "P(N)",
    "ΔΛ (ref-days)",
    height,
  );
}

export function renderThermalModeLottery(
  container: HTMLElement,
  config: Pick<SimConfig, "arrival_product" | "transit_temp_bias_c">,
  height = 168,
): void {
  const dMed = expectedDurationDays(config.arrival_product);
  const modes = ["cool", "nominal", "warm"] as const;
  const bars: LotteryBar[] = modes.map((mode) => ({
    label: mode.charAt(0).toUpperCase() + mode.slice(1),
    pmf: ARRIVAL_PREVIEW_DEFAULTS.thermalModes[mode].p,
    lambda: lambdaClean(dMed, phiSetForThermalMode(mode, config.transit_temp_bias_c)),
    highlight: mode === "nominal",
  }));
  renderDualAxisLottery(
    container,
    `Thermal mode lottery · ΔT=${config.transit_temp_bias_c >= 0 ? "+" : ""}${config.transit_temp_bias_c.toFixed(1)} °C`,
    bars,
    "trip thermal mode",
    "P(mode)",
    "Λ (ref-days)",
    height,
  );
}

import * as d3 from "d3";
import type { ControllerPolicy } from "../controls";
import type { DemandSummary, ScheduleWire } from "../engine/types";
import {
  dowSeriesFromDemandSummary,
  nbPmf,
  projectedDemandDays,
  protectionCoverageFromSchedule,
  type ProjectedDemandRow,
} from "./demandDist";

/** Fallback effective inventory when belief is unavailable (demo constant). */
export const DEMO_EFFECTIVE_INVENTORY = 42;

const FALLBACK_SUMMARY: DemandSummary = {
  scale_mu: 30,
  dow_means: [30, 30, 30, 30, 30, 30, 30],
};

export type DampedSwDecomposition = {
  effectiveInventory: number;
  targetQuantile: number;
  gap: number;
  rawOrder: number;
  orderQty: number;
  protectionDays: number;
  windowRows: ProjectedDemandRow[];
};

/** Snap order quantity to case multiples (matches studio snapOrder). */
export function caseRound(qty: number, caseSize: number): number {
  const cs = Math.max(1, Math.round(caseSize));
  if (qty <= 0) return 0;
  return Math.round(qty / cs) * cs;
}

function quantileFromPmf(pmf: { k: number; p: number }[], q: number): number {
  let cum = 0;
  for (const row of pmf) {
    cum += row.p;
    if (cum >= q) return row.k;
  }
  return pmf[pmf.length - 1]?.k ?? 0;
}

function convolvePmfs(
  a: { k: number; p: number }[],
  b: { k: number; p: number }[],
): { k: number; p: number }[] {
  const out = new Map<number, number>();
  for (const rowA of a) {
    for (const rowB of b) {
      const k = rowA.k + rowB.k;
      out.set(k, (out.get(k) ?? 0) + rowA.p * rowB.p);
    }
  }
  return [...out.entries()]
    .map(([k, p]) => ({ k, p }))
    .sort((x, y) => x.k - y.k);
}

function homogeneousProtectionPmf(
  mu: number,
  demandVm: number,
  protectionDays: number,
): { k: number; p: number }[] {
  if (protectionDays <= 0) return [{ k: 0, p: 1 }];
  const safeMu = Math.max(0.1, mu);
  const safeVm = Math.max(1.05, demandVm);
  const rDay = safeMu / (safeVm - 1);
  const rSum = rDay * protectionDays;
  const successP = rDay / (rDay + safeMu);
  const maxK = Math.min(
    400,
    Math.ceil(safeMu * protectionDays + 8 * Math.sqrt(safeMu * safeVm * protectionDays) + 30),
  );
  const out: { k: number; p: number }[] = [];
  let pk = successP ** rSum;
  let sum = 0;
  for (let k = 0; k <= maxK; k += 1) {
    out.push({ k, p: pk });
    sum += pk;
    pk *= ((k + rSum) / (k + 1)) * (1 - successP);
    if (pk < 1e-12 && k > safeMu * protectionDays) break;
  }
  if (sum > 0) {
    for (const row of out) row.p /= sum;
  }
  return out;
}

/** Homogeneous NB sum closed form: NB(n·r_day, p) quantile. */
export function homogeneousProtectionQuantile(
  alpha: number,
  mu: number,
  demandVm: number,
  protectionDays: number,
): number {
  if (protectionDays <= 0) return 0;
  return quantileFromPmf(
    homogeneousProtectionPmf(mu, demandVm, protectionDays),
    alpha,
  );
}

/** PMF of total demand over the protection window (NB convolution). */
export function protectionDemandPmf(
  demandVm: number,
  protectionDays: number,
  mus: readonly number[],
): { k: number; p: number }[] {
  if (protectionDays <= 0 || mus.length === 0) return [{ k: 0, p: 1 }];
  const prot = Math.min(protectionDays, mus.length);
  const windowMus = mus.slice(0, prot);
  const muMin = Math.min(...windowMus);
  const muMax = Math.max(...windowMus);
  if (muMax - muMin <= 1e-9) {
    return homogeneousProtectionPmf(muMin, demandVm, prot);
  }
  let combined = [{ k: 0, p: 1 }];
  for (const mu of windowMus) {
    combined = convolvePmfs(combined, nbPmf(mu, demandVm));
  }
  return combined;
}

/**
 * Alpha-quantile of protection-window NB demand.
 * Homogeneous closed-form when DOW means are flat; NB convolution otherwise.
 */
export function protectionDemandQuantile(
  alpha: number,
  demandVm: number,
  protectionDays: number,
  mus: readonly number[],
): number {
  if (protectionDays <= 0 || mus.length === 0) return 0;
  return quantileFromPmf(
    protectionDemandPmf(demandVm, protectionDays, mus),
    alpha,
  );
}

/**
 * Directional coverage bias: 0 = stockout-leaning, 1 = spoilage-leaning.
 * Monotone in both α and ρ on their slider ranges.
 */
const RHO_SLIDER_MIN = 0.5;
const RHO_SLIDER_MAX = 2.0;

export function coverageBiasScore(alpha: number, rho: number): number {
  const aNorm = (alpha - 0.5) / (0.99 - 0.5);
  const rNorm = (rho - RHO_SLIDER_MIN) / (RHO_SLIDER_MAX - RHO_SLIDER_MIN);
  return Math.min(1, Math.max(0, (aNorm + rNorm) / 2));
}

function defaultProtectionDays(
  episodeDay: number,
  schedule: ScheduleWire | null | undefined,
): number {
  if (schedule) {
    const rows = protectionCoverageFromSchedule(schedule);
    const wd = episodeDay % 7;
    const match = rows.find((r) => r.order_weekday === wd);
    if (match) return match.demand_days;
    if (rows.length > 0) return rows[0]!.demand_days;
  }
  return 3;
}

function windowMus(
  summary: DemandSummary,
  episodeDay: number,
  protectionDays: number,
): number[] {
  const series = dowSeriesFromDemandSummary(summary);
  const mus: number[] = [];
  for (let k = 0; k < protectionDays; k += 1) {
    const wd = (episodeDay + k) % 7;
    mus.push(series[wd] ?? summary.scale_mu);
  }
  return mus;
}

/** Compute damped_sw decomposition for the demo chart. */
export function computeDampedSwDecomposition(opts: {
  alpha: number;
  rho: number;
  caseSize: number;
  demandVm: number;
  demandSummary: DemandSummary | null | undefined;
  schedule: ScheduleWire | null | undefined;
  episodeDay: number;
  effectiveInventory: number;
}): DampedSwDecomposition {
  const summary = opts.demandSummary ?? FALLBACK_SUMMARY;
  const protectionDays = defaultProtectionDays(opts.episodeDay, opts.schedule);
  const windowRows = projectedDemandDays(
    opts.episodeDay,
    summary,
    protectionDays,
  );
  const mus = windowMus(summary, opts.episodeDay, protectionDays);
  const targetQuantile = protectionDemandQuantile(
    opts.alpha,
    opts.demandVm,
    protectionDays,
    mus,
  );
  const gap = Math.max(0, targetQuantile - opts.effectiveInventory);
  const rawOrder = gap * opts.rho;
  const orderQty = caseRound(rawOrder, opts.caseSize);
  return {
    effectiveInventory: opts.effectiveInventory,
    targetQuantile,
    gap,
    rawOrder,
    orderQty,
    protectionDays,
    windowRows,
  };
}

export type DampedSwDemoOpts = {
  alpha: number;
  rho: number;
  policy: ControllerPolicy;
  caseSize: number;
  demandVm: number;
  demandSummary: DemandSummary | null | undefined;
  schedule: ScheduleWire | null | undefined;
  episodeDay: number;
  effectiveInventory: number | null;
};

/** Interactive damped_sw teaching chart for the Autopilot tuning pane. */
export function renderDampedSwDemo(
  container: HTMLElement,
  opts: DampedSwDemoOpts,
  height = 240,
): void {
  const width = container.clientWidth > 60 ? container.clientWidth : 360;
  const margin = { top: 20, right: 12, bottom: 36, left: 40 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  container.replaceChildren();
  if (innerW <= 0) return;

  if (opts.policy === "constant") return;

  const effective =
    opts.effectiveInventory ?? DEMO_EFFECTIVE_INVENTORY;
  const decomp = computeDampedSwDecomposition({
    ...opts,
    effectiveInventory: effective,
  });

  const svg = d3
    .select(container)
    .append("svg")
    .attr("class", "chart-svg damped-sw-demo")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .attr("height", height)
    .attr(
      "aria-label",
      "Protection-interval demand histogram with target quantile and order markers",
    );

  const root = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const summary = opts.demandSummary ?? FALLBACK_SUMMARY;
  const mus = windowMus(summary, opts.episodeDay, decomp.protectionDays);
  const pmf = protectionDemandPmf(opts.demandVm, decomp.protectionDays, mus);

  const targetColor = "#f59e0b";
  const orderColor = "#2563eb";

  const xMax = Math.max(
    d3.max(pmf, (d) => d.k) ?? 1,
    decomp.targetQuantile,
    decomp.orderQty,
    1,
  ) * 1.06;
  const yMax = (d3.max(pmf, (d) => d.p) ?? 0.1) * 1.12;

  const x = d3.scaleLinear().domain([0, xMax]).nice().range([0, innerW]);
  const y = d3.scaleLinear().domain([0, yMax]).nice().range([innerH, 0]);

  const barW = Math.max(1, innerW / Math.max(pmf.length, 1) - 0.5);

  root
    .selectAll(".prot-demand-hist-bar")
    .data(pmf.filter((d) => d.p > 1e-12))
    .join("rect")
    .attr("class", "prot-demand-hist-bar")
    .attr("x", (d) => x(d.k) - barW / 2)
    .attr("y", (d) => y(d.p))
    .attr("width", barW)
    .attr("height", (d) => Math.max(0, y(0) - y(d.p)))
    .attr("fill", "var(--chart-band, #dbeafe)");

  const markerY1 = 0;
  const markerY2 = innerH;

  root
    .append("line")
    .attr("class", "damped-sw-marker damped-sw-marker--target")
    .attr("x1", x(decomp.targetQuantile))
    .attr("x2", x(decomp.targetQuantile))
    .attr("y1", markerY1)
    .attr("y2", markerY2)
    .attr("stroke", targetColor)
    .attr("stroke-width", 2);

  root
    .append("line")
    .attr("class", "damped-sw-marker damped-sw-marker--order")
    .attr("x1", x(decomp.orderQty))
    .attr("x2", x(decomp.orderQty))
    .attr("y1", markerY1)
    .attr("y2", markerY2)
    .attr("stroke", orderColor)
    .attr("stroke-width", 2);

  root
    .append("g")
    .attr("class", "axis axis-y")
    .call(d3.axisLeft(y).ticks(4).tickFormat(d3.format(".2f")).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").remove());

  root
    .append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0))
    .call((sel) => sel.select(".domain").attr("stroke-opacity", 0.35));

  root
    .append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 28)
    .attr("text-anchor", "middle")
    .attr("font-size", "10px")
    .text(`Protection demand (${decomp.protectionDays} days)`);

  const legend = svg
    .append("g")
    .attr("class", "legend damped-sw-legend")
    .attr("transform", `translate(${margin.left + 4}, 4)`);

  const legendItems = [
    { label: `F⁻¹(α) ${decomp.targetQuantile.toFixed(0)}`, color: targetColor },
    { label: `q ${decomp.orderQty}`, color: orderColor },
  ];

  legendItems.forEach((item, i) => {
    const itemG = legend
      .append("g")
      .attr("class", "damped-sw-legend-item")
      .attr("transform", `translate(${i * 88},0)`);
    itemG
      .append("line")
      .attr("x1", 0)
      .attr("x2", 12)
      .attr("y1", 6)
      .attr("y2", 6)
      .attr("stroke", item.color)
      .attr("stroke-width", 2);
    itemG
      .append("text")
      .attr("class", "legend-label")
      .attr("x", 16)
      .attr("y", 9)
      .attr("font-size", "10px")
      .text(item.label);
  });
}

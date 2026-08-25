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

/** Homogeneous NB sum closed form: NB(n·r_day, p) quantile. */
export function homogeneousProtectionQuantile(
  alpha: number,
  mu: number,
  demandVm: number,
  protectionDays: number,
): number {
  if (protectionDays <= 0) return 0;
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
  return quantileFromPmf(out, alpha);
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
  const prot = Math.min(protectionDays, mus.length);
  const windowMus = mus.slice(0, prot);
  const muMin = Math.min(...windowMus);
  const muMax = Math.max(...windowMus);
  if (muMax - muMin <= 1e-9) {
    return homogeneousProtectionQuantile(alpha, muMin, demandVm, prot);
  }
  let combined = [{ k: 0, p: 1 }];
  for (const mu of windowMus) {
    combined = convolvePmfs(combined, nbPmf(mu, demandVm));
  }
  return quantileFromPmf(combined, alpha);
}

/**
 * Directional coverage bias: 0 = stockout-leaning, 1 = spoilage-leaning.
 * Monotone in both α and ρ on their slider ranges.
 */
export function coverageBiasScore(alpha: number, rho: number): number {
  const aNorm = (alpha - 0.5) / (0.99 - 0.5);
  const rNorm = (rho - 0.1) / (1.0 - 0.1);
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
  height = 320,
): void {
  const width = container.clientWidth > 60 ? container.clientWidth : 360;
  const margin = { top: 12, right: 12, bottom: 8, left: 8 };
  const innerW = width - margin.left - margin.right;

  container.replaceChildren();
  if (innerW <= 0) return;

  const disabled = opts.policy === "constant";
  const effective =
    opts.effectiveInventory ?? DEMO_EFFECTIVE_INVENTORY;
  const decomp = disabled
    ? null
    : computeDampedSwDecomposition({
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
      "Damped survival-weighted controller decomposition demo",
    );

  const root = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  if (disabled) {
    root
      .append("text")
      .attr("class", "damped-sw-demo-hint")
      .attr("x", innerW / 2)
      .attr("y", height / 2 - margin.top)
      .attr("text-anchor", "middle")
      .text("Constant policy — α / ρ apply to damped_sw only");
    return;
  }

  if (!decomp) return;

  const panelH = (height - margin.top - margin.bottom) / 4;
  let yOff = 0;

  // Panel 1: protection-window demand strip (fixed horizon)
  const stripG = root.append("g").attr("transform", `translate(0,${yOff})`);
  stripG
    .append("text")
    .attr("class", "axis-label")
    .attr("x", 0)
    .attr("y", 10)
    .text(`Protection window demand (${decomp.protectionDays} days)`);

  const stripInnerH = panelH - 22;
  const xBand = d3
    .scaleBand<string>()
    .domain(decomp.windowRows.map((r) => r.weekday))
    .range([0, innerW])
    .padding(0.18);
  const yStrip = d3
    .scaleLinear()
    .domain([
      0,
      (d3.max(decomp.windowRows, (r) => r.mean) ?? 1) * 1.15,
    ])
    .nice()
    .range([stripInnerH, 16]);

  stripG
    .selectAll(".prot-demand-bar")
    .data(decomp.windowRows)
    .join("rect")
    .attr("class", "prot-demand-bar")
    .attr("x", (d) => xBand(d.weekday) ?? 0)
    .attr("y", (d) => yStrip(d.mean))
    .attr("width", xBand.bandwidth())
    .attr("height", (d) => Math.max(0, stripInnerH - yStrip(d.mean) + 16))
    .attr("fill", "var(--chart-band, #dbeafe)");

  stripG
    .selectAll(".prot-demand-label")
    .data(decomp.windowRows)
    .join("text")
    .attr("class", "prot-demand-label")
    .attr("x", (d) => (xBand(d.weekday) ?? 0) + xBand.bandwidth() / 2)
    .attr("y", stripInnerH + 14)
    .attr("text-anchor", "middle")
    .attr("font-size", "9px")
    .text((d) => `${d.weekday} μ=${d.mean.toFixed(0)}`);

  yOff += panelH;

  // Panel 2: decomposition number line
  const decompG = root.append("g").attr("transform", `translate(0,${yOff})`);
  decompG
    .append("text")
    .attr("class", "axis-label")
    .attr("x", 0)
    .attr("y", 10)
    .text("Controller decomposition");

  const maxVal = Math.max(
    decomp.targetQuantile,
    decomp.effectiveInventory + decomp.orderQty,
    1,
  );
  const xNum = d3.scaleLinear().domain([0, maxVal * 1.08]).range([0, innerW]);
  const baseY = panelH * 0.55;

  const markers: { key: string; value: number; label: string; cls: string }[] =
    [
      {
        key: "i",
        value: decomp.effectiveInventory,
        label: `Ĩ ${decomp.effectiveInventory.toFixed(0)}`,
        cls: "damped-sw-marker--inv",
      },
      {
        key: "d",
        value: decomp.targetQuantile,
        label: `F⁻¹(α) ${decomp.targetQuantile.toFixed(0)}`,
        cls: "damped-sw-marker--target",
      },
      {
        key: "post",
        value: decomp.effectiveInventory + decomp.orderQty,
        label: `Ĩ+q ${(decomp.effectiveInventory + decomp.orderQty).toFixed(0)}`,
        cls: "damped-sw-marker--post",
      },
    ];

  decompG
    .append("line")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("y1", baseY)
    .attr("y2", baseY)
    .attr("stroke", "var(--paper-edge, #d1d5db)")
    .attr("stroke-width", 1);

  decompG
    .selectAll(".damped-sw-marker")
    .data(markers)
    .join("g")
    .attr("class", (d) => `damped-sw-marker ${d.cls}`)
    .each(function (d) {
      const g = d3.select(this);
      const cx = xNum(d.value);
      g.append("line")
        .attr("x1", cx)
        .attr("x2", cx)
        .attr("y1", baseY - 14)
        .attr("y2", baseY + 14)
        .attr("stroke-width", 2);
      g.append("text")
        .attr("x", cx)
        .attr("y", baseY - 18)
        .attr("text-anchor", "middle")
        .attr("font-size", "9px")
        .text(d.label);
    });

  decompG
    .append("text")
    .attr("x", 0)
    .attr("y", panelH - 4)
    .attr("font-size", "9px")
    .text(
      `gap ${decomp.gap.toFixed(1)} · ρ·gap ${decomp.rawOrder.toFixed(1)} · q ${decomp.orderQty}`,
    );

  yOff += panelH;

  // Panel 3: coverage tendency gauge
  const gaugeG = root.append("g").attr("transform", `translate(0,${yOff})`);
  const bias = coverageBiasScore(opts.alpha, opts.rho);
  const gaugeW = innerW;
  const gaugeY = 14;

  gaugeG
    .append("text")
    .attr("class", "axis-label")
    .attr("x", 0)
    .attr("y", 10)
    .text("Coverage tendency");

  const grad = gaugeG
    .append("defs")
    .append("linearGradient")
    .attr("id", "damped-sw-bias-grad")
    .attr("x1", "0%")
    .attr("x2", "100%");
  grad.append("stop").attr("offset", "0%").attr("stop-color", "#dc2626");
  grad.append("stop").attr("offset", "100%").attr("stop-color", "#16a34a");

  gaugeG
    .append("rect")
    .attr("x", 0)
    .attr("y", gaugeY)
    .attr("width", gaugeW)
    .attr("height", 10)
    .attr("rx", 5)
    .attr("fill", "url(#damped-sw-bias-grad)")
    .attr("opacity", 0.85);

  gaugeG
    .append("circle")
    .attr("class", "damped-sw-bias-handle")
    .attr("cx", bias * gaugeW)
    .attr("cy", gaugeY + 5)
    .attr("r", 6)
    .attr("fill", "#f59e0b")
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.5);

  gaugeG
    .append("text")
    .attr("x", 0)
    .attr("y", gaugeY + 26)
    .attr("font-size", "9px")
    .text("stockout-leaning");

  gaugeG
    .append("text")
    .attr("x", gaugeW)
    .attr("y", gaugeY + 26)
    .attr("text-anchor", "end")
    .attr("font-size", "9px")
    .text("spoilage-leaning");

  yOff += panelH;

  // Panel 4: post-order position vs target
  const posG = root.append("g").attr("transform", `translate(0,${yOff})`);
  posG
    .append("text")
    .attr("class", "axis-label")
    .attr("x", 0)
    .attr("y", 10)
    .text("Post-order position vs target");

  const barH = panelH - 28;
  const yPos = d3
    .scaleLinear()
    .domain([0, maxVal * 1.08])
    .range([barH + 16, 16]);

  posG
    .append("rect")
    .attr("class", "damped-sw-post-bar")
    .attr("x", 0)
    .attr("y", yPos(decomp.effectiveInventory + decomp.orderQty))
    .attr("width", innerW * 0.55)
    .attr("height", Math.max(
      0,
      yPos(decomp.effectiveInventory) - yPos(decomp.effectiveInventory + decomp.orderQty),
    ))
    .attr("fill", "var(--chart-accent, #2563eb)")
    .attr("opacity", 0.75);

  posG
    .append("line")
    .attr("class", "damped-sw-target-line")
    .attr("x1", xNum(decomp.targetQuantile))
    .attr("x2", xNum(decomp.targetQuantile))
    .attr("y1", 16)
    .attr("y2", barH + 16)
    .attr("stroke", "#f59e0b")
    .attr("stroke-width", 2)
    .attr("stroke-dasharray", "4,3");

  posG
    .append("text")
    .attr("x", xNum(decomp.targetQuantile) + 4)
    .attr("y", 24)
    .attr("font-size", "9px")
    .text("target");
}

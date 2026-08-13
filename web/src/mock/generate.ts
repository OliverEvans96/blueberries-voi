import type {
  ArrivalProduct,
  BeliefGrid,
  Day,
  Economics,
  Lot,
  ScenarioId,
  SimConfig,
} from "../types";

export const DEFAULT_ECONOMICS: Economics = {
  p_sell: 4.5,
  c_unit: 1.8,
  c_waste: 1.2,
  c_stockout: 2.5,
};

/**
 * Abdella shipment effective ages at ModelParams defaults (q10=3, t_ref=0°C),
 * from shipment_arrival_age on the six MOD-21 traces (S1…S6).
 */
const ABDELLA_AGES_BASE: Record<string, number> = {
  S1: 6.067,
  S2: 2.449, // FL short-haul
  S3: 8.462,
  S4: 7.661,
  S5: 8.376,
  S6: 6.033,
};

const LONG_HAUL_IDS = ["S1", "S3", "S4", "S5", "S6"] as const;
const SHORT_HAUL_IDS = ["S2"] as const;
const ALL_IDS = ["S1", "S2", "S3", "S4", "S5", "S6"] as const;

/** Defaults aligned with blueberries_voi.model.ModelParams where applicable. */
export const DEFAULT_SIM_CONFIG: SimConfig = {
  beta: 2,
  eta_ref: 14,
  q10: 3,
  t_ref_c: 0,
  t_store_c: 4,
  sigma: 0.5,
  demand_mu: 30,
  demand_vm: 2,
  case_size: 8,
  lead_time: 1,
  base_stock: 48,
  starting_inv: 72,
  seed: 42,
  obs_scenario: "P1",
  window_days: 14,
  arrival_product: "abdella_all",
  spread_scale: 1,
  transit_temp_bias_c: 0,
  f2a_transit_sd: 0.75,
  sensor_sigma: 0,
};

export type SimState = {
  day: number;
  lots: Lot[];
  nextLotId: number;
  pendingOrders: { arriveOn: number; qty: number }[];
  history: Day[];
  rng: () => number;
  config: SimConfig;
};

function mulberry32(seed: number): () => number {
  let t = seed >>> 0;
  return () => {
    t += 0x6d2b79f5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

function gaussian(rng: () => number): number {
  // Box–Muller
  const u = Math.max(1e-12, rng());
  const v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function productShipmentIds(product: ArrivalProduct): readonly string[] {
  if (product === "long_haul") return LONG_HAUL_IDS;
  if (product === "short_haul") return SHORT_HAUL_IDS;
  return ALL_IDS;
}

/** Arrhenius scale vs published cold traces (MOD-18 teaching bias). */
function transitAgeFactor(cfg: SimConfig): number {
  const q10 = Math.max(1.01, cfg.q10);
  return q10 ** (cfg.transit_temp_bias_c / 10);
}

/** Base mix ages after Q10 rescale from the q10=3 calibration point. */
function baseMixAges(cfg: SimConfig): number[] {
  const ids = productShipmentIds(cfg.arrival_product);
  const q10Scale = Math.max(1.01, cfg.q10) / 3;
  // Mild Q10 rescale of integrated ages (mock stand-in for re-integrating paths).
  return ids.map((id) => ABDELLA_AGES_BASE[id]! * q10Scale);
}

/**
 * Pushforward arrival-age samples (MOD-11=C / generate_arrival_age):
 * bootstrap mix → shrink by spread_scale → transit temp bias → sensor noise.
 */
export function sampleArrivalAge(cfg: SimConfig, rng: () => number): number {
  const ages = baseMixAges(cfg);
  const mean = ages.reduce((s, a) => s + a, 0) / ages.length;
  const raw = ages[Math.floor(rng() * ages.length)]!;
  const scaled = mean + cfg.spread_scale * (raw - mean);
  const withTransit = scaled * transitAgeFactor(cfg);
  const noisy =
    cfg.sensor_sigma > 0
      ? withTransit + gaussian(rng) * cfg.sensor_sigma
      : withTransit;
  return clamp(noisy, 0, 14);
}

/** Discrete prior PMF on a uniform age grid (FIL-03-style teaching view). */
export function arrivalAgePriorPdf(
  cfg: SimConfig,
  opts?: { transitBiasOverride?: number; nGrid?: number },
): { tau: number; density: number }[] {
  const nGrid = opts?.nGrid ?? 81;
  const tauMax = 12;
  const bias =
    opts?.transitBiasOverride !== undefined
      ? opts.transitBiasOverride
      : cfg.transit_temp_bias_c;
  const factor = Math.max(1.01, cfg.q10) ** (bias / 10);
  const mix = baseMixAges(cfg);
  const ages = mix.map((a) => meanShrink(a, mix, cfg.spread_scale) * factor);
  const bw = Math.max(0.15, cfg.f2a_transit_sd * 0.55);
  const dx = tauMax / (nGrid - 1);
  const pts: { tau: number; density: number }[] = [];
  for (let i = 0; i < nGrid; i++) {
    const tau = i * dx;
    let dens = 0;
    for (const a of ages) {
      const z = (tau - a) / bw;
      dens += Math.exp(-0.5 * z * z);
    }
    dens /= ages.length * bw * Math.sqrt(2 * Math.PI);
    pts.push({ tau, density: dens });
  }
  let mass = 0;
  for (const p of pts) mass += p.density * dx;
  if (mass > 0) for (const p of pts) p.density /= mass;
  return pts;
}

function meanShrink(age: number, mix: number[], spreadScale: number): number {
  const mean = mix.reduce((s, a) => s + a, 0) / mix.length;
  return mean + spreadScale * (age - mean);
}

/** F2a-style Gaussian centered on mix mean (pack-date prior width). */
export function f2aPriorPdf(
  cfg: SimConfig,
  nGrid = 81,
): { tau: number; density: number }[] {
  const mix = baseMixAges(cfg);
  const ages = mix.map((a) => meanShrink(a, mix, cfg.spread_scale));
  const mean =
    (ages.reduce((s, a) => s + a, 0) / ages.length) * transitAgeFactor(cfg);
  const sd = Math.max(0.05, cfg.f2a_transit_sd);
  const tauMax = 12;
  const pts: { tau: number; density: number }[] = [];
  const dx = tauMax / (nGrid - 1);
  for (let i = 0; i < nGrid; i++) {
    const tau = i * dx;
    const z = (tau - mean) / sd;
    pts.push({
      tau,
      density: Math.exp(-0.5 * z * z) / (sd * Math.sqrt(2 * Math.PI)),
    });
  }
  return pts;
}

export function snapCases(qty: number, caseSize: number): number {
  if (qty <= 0) return 0;
  const cs = Math.max(1, Math.round(caseSize));
  return Math.round(qty / cs) * cs;
}

function totalInventory(lots: Lot[]): number {
  return lots.reduce((s, l) => s + l.n, 0);
}

/** Effective characteristic life under Q10 temperature shift. */
export function etaEffective(cfg: SimConfig): number {
  const shift = (cfg.t_ref_c - cfg.t_store_c) / 10;
  return Math.max(0.5, cfg.eta_ref * cfg.q10 ** shift);
}

function weibullSurvival(t: number, beta: number, eta: number): number {
  if (t <= 0) return 1;
  return Math.exp(-((t / eta) ** beta));
}

export { weibullSurvival };

/** Deterministic Weibull survival curve under current Q10-adjusted η. */
export function survivalCurve(
  cfg: SimConfig,
  tauMax = 24,
  steps = 97,
): { tau: number; s: number; h: number }[] {
  const eta = etaEffective(cfg);
  const pts: { tau: number; s: number; h: number }[] = [];
  for (let i = 0; i <= steps; i++) {
    const tau = (i / steps) * tauMax;
    const s = weibullSurvival(tau, cfg.beta, eta);
    const s1 = weibullSurvival(tau + 1e-3, cfg.beta, eta);
    const h = s > 1e-12 ? Math.max(0, (s - s1) / (1e-3 * s)) : 0;
    pts.push({ tau, s, h });
  }
  return pts;
}

/** NB pmf under ModelParams convention (no seasonal factor — knob snapshot). */
export function demandPmf(
  cfg: SimConfig,
  kMax?: number,
): { k: number; p: number }[] {
  const mu = Math.max(0.1, cfg.demand_mu);
  const vm = Math.max(1.05, cfg.demand_vm);
  const r = mu / (vm - 1);
  const successP = r / (r + mu);
  const maxK = kMax ?? Math.min(200, Math.ceil(mu + 8 * Math.sqrt(mu * vm) + 20));

  const out: { k: number; p: number }[] = [];
  // Recurrence: P(0)=p^r; P(k+1)/P(k) = (k+r)/(k+1) * (1-p)
  let pk = successP ** r;
  let sum = 0;
  for (let k = 0; k <= maxK; k++) {
    out.push({ k, p: pk });
    sum += pk;
    pk *= ((k + r) / (k + 1)) * (1 - successP);
    if (pk < 1e-12 && k > mu) break;
  }
  if (sum > 0) {
    for (const row of out) row.p /= sum;
  }
  return out;
}

export function survivalWeightedInventory(
  lots: Lot[],
  cfg: SimConfig,
): number {
  const eta = etaEffective(cfg);
  return lots.reduce(
    (s, l) => s + l.n * weibullSurvival(l.tau, cfg.beta, eta),
    0,
  );
}

export function onHandInventory(lots: Lot[]): number {
  return totalInventory(lots);
}


/** Per-day spoil probability from Weibull survival ratio, with sigma noise. */
function spoilProb(tau: number, cfg: SimConfig, rng: () => number): number {
  const eta = etaEffective(cfg) * Math.exp(cfg.sigma * (rng() - 0.5) * 0.4);
  const s0 = weibullSurvival(tau, cfg.beta, eta);
  const s1 = weibullSurvival(tau + 1, cfg.beta, eta);
  if (s0 <= 1e-12) return 1;
  return clamp(1 - s1 / s0, 0, 1);
}

function binomialTrials(n: number, p: number, rng: () => number): number {
  if (n <= 0 || p <= 0) return 0;
  if (p >= 1) return n;
  let k = 0;
  for (let i = 0; i < n; i++) {
    if (rng() < p) k += 1;
  }
  return k;
}

/** Age one day; Weibull-ish spoilage draws waste from each lot. */
function ageAndSpoil(
  lots: Lot[],
  cfg: SimConfig,
  rng: () => number,
): { lots: Lot[]; waste: number } {
  let waste = 0;
  const next: Lot[] = [];
  for (const lot of lots) {
    const tau = lot.tau + 1;
    const p = spoilProb(tau, cfg, rng);
    const died = binomialTrials(lot.n, p, rng);
    waste += died;
    const left = lot.n - died;
    if (left > 0) next.push({ lot_id: lot.lot_id, n: left, tau });
  }
  return { lots: next, waste };
}

function applySales(
  lots: Lot[],
  demand: number,
): { lots: Lot[]; sales: number; stockout: number } {
  let remaining = demand;
  let sales = 0;
  const next: Lot[] = [];
  const ordered = [...lots].sort((a, b) => a.tau - b.tau || a.lot_id - b.lot_id);
  for (const lot of ordered) {
    if (remaining <= 0) {
      next.push(lot);
      continue;
    }
    const take = Math.min(lot.n, remaining);
    sales += take;
    remaining -= take;
    const left = lot.n - take;
    if (left > 0) next.push({ ...lot, n: left });
  }
  return { lots: next, sales, stockout: remaining };
}

/** Marsaglia polar normal. */
function randn(rng: () => number): number {
  let u = 0;
  let v = 0;
  let s = 0;
  do {
    u = rng() * 2 - 1;
    v = rng() * 2 - 1;
    s = u * u + v * v;
  } while (s >= 1 || s === 0);
  return u * Math.sqrt((-2 * Math.log(s)) / s);
}

/** Approx Gamma(shape, scale) via sum-of-exponentials / normal for large shape. */
function sampleGamma(rng: () => number, shape: number, scale: number): number {
  if (shape < 1) {
    const u = Math.max(1e-12, rng());
    return sampleGamma(rng, shape + 1, scale) * u ** (1 / shape);
  }
  // Marsaglia-Tsang
  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);
  for (;;) {
    let x: number;
    let v: number;
    do {
      x = randn(rng);
      v = 1 + c * x;
    } while (v <= 0);
    v = v * v * v;
    const u = rng();
    if (u < 1 - 0.0331 * (x * x) * (x * x)) return d * v * scale;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v * scale;
  }
}

function samplePoisson(rng: () => number, lambda: number): number {
  if (lambda <= 0) return 0;
  if (lambda > 30) {
    return Math.max(0, Math.round(lambda + Math.sqrt(lambda) * randn(rng)));
  }
  const L = Math.exp(-lambda);
  let k = 0;
  let p = 1;
  do {
    k += 1;
    p *= rng();
  } while (p > L);
  return k - 1;
}

/** Negative-binomial-ish demand from mean + V/M (ModelParams convention). */
function sampleDemand(
  rng: () => number,
  cfg: SimConfig,
  day: number,
): number {
  const seasonal = 1 + 0.18 * Math.sin(day / 3);
  const mu = Math.max(0.1, cfg.demand_mu * seasonal);
  const vm = Math.max(1.05, cfg.demand_vm);
  const r = mu / (vm - 1);
  const lam = sampleGamma(rng, r, mu / r);
  return samplePoisson(rng, lam);
}

function beliefBlur(scenario: ScenarioId): number {
  if (scenario === "P0") return 1.6;
  if (scenario === "F2") return 0.55;
  if (scenario === "F2a") return 0.7;
  if (scenario === "F1s") return 0.85;
  if (scenario === "F1") return 0.95;
  return 1; // P1
}

export function generateBelief(
  lots: Lot[],
  rng: () => number,
  scenario: ScenarioId = "P1",
): BeliefGrid {
  const tauBins = 12;
  const countBins = 10;
  const tau_edges = Array.from({ length: tauBins + 1 }, (_, i) => i);
  const maxCount = Math.max(40, totalInventory(lots) * 1.4);
  const count_edges = Array.from(
    { length: countBins + 1 },
    (_, i) => (i / countBins) * maxCount,
  );
  const blur = beliefBlur(scenario);

  const density: number[][] = Array.from({ length: tauBins }, () =>
    Array.from({ length: countBins }, () => 0),
  );

  const byAge = new Map<number, number>();
  for (const lot of lots) {
    byAge.set(lot.tau, (byAge.get(lot.tau) ?? 0) + lot.n);
  }

  for (let ti = 0; ti < tauBins; ti++) {
    const tauCenter = (tau_edges[ti]! + tau_edges[ti + 1]!) / 2;
    for (let ci = 0; ci < countBins; ci++) {
      const countCenter = (count_edges[ci]! + count_edges[ci + 1]!) / 2;
      let mass = 0.02 * blur; // prior floor
      for (const [tau, n] of byAge) {
        const dTau = (tauCenter - tau) / blur;
        const dN = (countCenter - n) / blur;
        mass += Math.exp(
          -(dTau * dTau) / 2.2 - (dN * dN) / (2 * (maxCount * 0.18) ** 2),
        );
      }
      mass *= 0.75 + 0.5 * rng();
      density[ti]![ci] = mass;
    }
  }

  let sum = 0;
  for (const row of density) for (const v of row) sum += v;
  if (sum > 0) {
    for (const row of density) {
      for (let i = 0; i < row.length; i++) row[i]! /= sum;
    }
  }

  return { tau_edges, count_edges, density };
}

function buildStartingLots(cfg: SimConfig, rng: () => number): Lot[] {
  const cs = Math.max(1, Math.round(cfg.case_size));
  const total = snapCases(cfg.starting_inv, cs);
  if (total <= 0) return [];
  const nLots = 3;
  const lots: Lot[] = [];
  let allocated = 0;
  for (let i = 0; i < nLots; i++) {
    const raw =
      i === nLots - 1
        ? total - allocated
        : snapCases(Math.round(total / nLots), cs);
    const n = Math.max(0, Math.min(total - allocated, raw));
    if (n > 0) {
      lots.push({
        lot_id: i + 1,
        n,
        tau: Math.round(sampleArrivalAge(cfg, rng) * 10) / 10,
      });
      allocated += n;
    }
  }
  if (allocated < total) {
    lots.push({
      lot_id: lots.length + 1,
      n: total - allocated,
      tau: Math.round(sampleArrivalAge(cfg, rng) * 10) / 10,
    });
  }
  return lots;
}

function runDay(
  day: number,
  lots: Lot[],
  pendingOrders: { arriveOn: number; qty: number }[],
  nextLotId: number,
  orderQty: number,
  cfg: SimConfig,
  rng: () => number,
  autopilot: boolean,
): {
  lots: Lot[];
  pendingOrders: { arriveOn: number; qty: number }[];
  nextLotId: number;
  record: Day;
} {
  let stateLots = lots;
  let nid = nextLotId;
  let pending = [...pendingOrders];

  const arrivals = pending
    .filter((o) => o.arriveOn === day)
    .reduce((s, o) => s + o.qty, 0);
  pending = pending.filter((o) => o.arriveOn !== day);
  let age_at_receipt: number | null = null;
  if (arrivals > 0) {
    age_at_receipt = Math.round(sampleArrivalAge(cfg, rng) * 100) / 100;
    stateLots = [
      ...stateLots,
      { lot_id: nid++, n: arrivals, tau: age_at_receipt },
    ];
  }

  const aged = ageAndSpoil(stateLots, cfg, rng);
  stateLots = aged.lots;
  const demand = sampleDemand(rng, cfg, day);
  const sold = applySales(stateLots, demand);
  stateLots = sold.lots;

  let order_qty = snapCases(Math.max(0, orderQty), cfg.case_size);
  if (autopilot) {
    const inv = totalInventory(stateLots);
    const target = snapCases(cfg.base_stock, cfg.case_size);
    order_qty = snapCases(
      clamp(target - inv, 0, target * 2),
      cfg.case_size,
    );
  }

  if (order_qty > 0) {
    pending.push({ arriveOn: day + Math.max(0, Math.round(cfg.lead_time)), qty: order_qty });
  }

  return {
    lots: stateLots,
    pendingOrders: pending,
    nextLotId: nid,
    record: {
      day,
      lots: stateLots.map((l) => ({ ...l })),
      sales_total: sold.sales,
      waste_total: aged.waste,
      demand,
      order_qty,
      arrivals,
      stockout: sold.stockout,
      age_at_receipt,
    },
  };
}

export function createInitialState(cfg: SimConfig): SimState {
  const config: SimConfig = { ...cfg };
  const rng = mulberry32(config.seed);
  let lots = buildStartingLots(config, rng);
  let nextLotId = lots.reduce((m, l) => Math.max(m, l.lot_id), 0) + 1;
  let pendingOrders: { arriveOn: number; qty: number }[] = [];
  const history: Day[] = [];
  let day = 0;

  for (let i = 0; i < config.window_days; i++) {
    day += 1;
    const stepped = runDay(
      day,
      lots,
      pendingOrders,
      nextLotId,
      0,
      config,
      rng,
      true,
    );
    lots = stepped.lots;
    pendingOrders = stepped.pendingOrders;
    nextLotId = stepped.nextLotId;
    history.push(stepped.record);
  }

  return {
    day,
    lots,
    nextLotId,
    pendingOrders,
    history,
    rng,
    config,
  };
}

export function stepSimulation(
  state: SimState,
  orderQtyRaw: number,
  cfg: SimConfig,
): { state: SimState; dayRecord: Day } {
  const config = { ...cfg };
  const day = state.day + 1;
  const stepped = runDay(
    day,
    state.lots,
    state.pendingOrders,
    state.nextLotId,
    orderQtyRaw,
    config,
    state.rng,
    false,
  );

  const history = [...state.history, stepped.record].slice(-config.window_days);

  return {
    state: {
      day,
      lots: stepped.lots,
      nextLotId: stepped.nextLotId,
      pendingOrders: stepped.pendingOrders,
      history,
      rng: state.rng,
      config,
    },
    dayRecord: stepped.record,
  };
}

export function computePnL(history: Day[], economics: Economics) {
  const series = history.map((d) => {
    const revenue = d.sales_total * economics.p_sell;
    const cost_purchase = d.arrivals * economics.c_unit;
    const cost_waste = d.waste_total * economics.c_waste;
    const cost_stockout = d.stockout * economics.c_stockout;
    const cost_total = cost_purchase + cost_waste + cost_stockout;
    return {
      day: d.day,
      revenue,
      cost_purchase,
      cost_waste,
      cost_stockout,
      cost_total,
      profit: revenue - cost_total,
    };
  });

  const revenue = series.reduce((s, d) => s + d.revenue, 0);
  const cost = series.reduce((s, d) => s + d.cost_total, 0);
  const today = series[series.length - 1];
  return {
    series,
    totals: {
      revenue,
      cost,
      profit: revenue - cost,
      today_revenue: today?.revenue ?? 0,
      today_cost: today?.cost_total ?? 0,
      today_profit: today?.profit ?? 0,
    },
  };
}

/** @deprecated use DEFAULT_SIM_CONFIG / DEFAULT_ECONOMICS */
export const MOCK_DEFAULTS = {
  CASE_SIZE: DEFAULT_SIM_CONFIG.case_size,
  WINDOW_DAYS: DEFAULT_SIM_CONFIG.window_days,
  LEAD_TIME: DEFAULT_SIM_CONFIG.lead_time,
  economics: DEFAULT_ECONOMICS,
};

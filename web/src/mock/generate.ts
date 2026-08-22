import type { FlatBelief } from "../engine/types";
import { scheduleFromConfig } from "../calendar/weekCalendar";
import type {
  ArrivalProduct,
  BeliefGrid,
  Day,
  Economics,
  Lot,
  ObsScenarioKey,
  ScenarioId,
  SimConfig,
  Unit,
  UnitExit,
} from "../types";
import { DEFAULT_OBS_CHANNELS } from "../obsMask";

export const DEFAULT_ECONOMICS: Economics = {
  p_sell: 4.5,
  c_unit: 1.8,
  c_waste: 1.2,
  c_stockout: 2.5,
};

/** Gamma aging defaults (ModelParams / voi_core). */
const GAMMA_SHAPE = 2.0;
const GAMMA_SCALE = 0.08;

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
  eta_ref: 14,
  q10: 3,
  t_ref_c: 0,
  t_store_c: 4,
  sigma: 0.5,
  demand_mu: 30,
  demand_vm: 2,
  case_size: 8,
  lead_time: 1,
  delivery_weekdays: [0, 2, 4],
  base_stock: 48,
  seed: 42,
  obs_scenario: "P1",
  obs_channels: DEFAULT_OBS_CHANNELS,
  window_days: 90,
  arrival_product: "abdella_all",
  spread_scale: 1,
  transit_temp_bias_c: 0,
  sensor_sigma: 0,
};

export type SimState = {
  day: number;
  lots: Lot[];
  units: Unit[];
  nextLotId: number;
  nextUnitId: number;
  pendingOrders: { arriveOn: number; qty: number }[];
  history: Day[];
  rng: () => number;
  config: SimConfig;
};

function aggregateLotsFromUnits(units: Unit[]): Lot[] {
  const byLot = new Map<number, { n: number; sumF: number }>();
  for (const u of units) {
    const cur = byLot.get(u.lot_id) ?? { n: 0, sumF: 0 };
    cur.n += 1;
    cur.sumF += u.f;
    byLot.set(u.lot_id, cur);
  }
  return [...byLot.entries()]
    .sort(([a], [b]) => a - b)
    .map(([lot_id, { n, sumF }]) => ({
      lot_id,
      n,
      mean_f: n > 0 ? sumF / n : 0,
    }));
}

function birthUnitsForLot(
  lotId: number,
  count: number,
  meanF: number,
  rng: () => number,
  nextUnitId: number,
): { units: Unit[]; nextUnitId: number } {
  const units: Unit[] = [];
  let uid = nextUnitId;
  const spread = 0.045;
  for (let i = 0; i < count; i++) {
    const f = clamp(meanF + randn(rng) * spread, 0, 1);
    units.push({
      unit_id: uid,
      lot_id: lotId,
      f: Math.round(f * 1000) / 1000,
    });
    uid += 1;
  }
  return { units, nextUnitId: uid };
}

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

/** Q10 store-aging factor (matches voi_core store_temp_factor). */
export function storeTempFactor(cfg: SimConfig): number {
  return Math.max(1.01, cfg.q10) ** ((cfg.t_store_c - cfg.t_ref_c) / 10);
}

/** Map effective age τ (days) to unit freshness f ∈ [0, 1]. */
export function ageToF(tauDays: number, etaRef: number): number {
  if (etaRef <= 0) return 0;
  return clamp(1 - tauDays / etaRef, 0, 1);
}

/** Base mix ages after Q10 rescale from the q10=3 calibration point. */
function baseMixAges(cfg: SimConfig): number[] {
  const ids = productShipmentIds(cfg.arrival_product);
  const q10Scale = Math.max(1.01, cfg.q10) / 3;
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
  return clamp(noisy, 0, cfg.eta_ref);
}

/** Freshness at receipt from the arrival-age mix. */
export function sampleArrivalFreshness(cfg: SimConfig, rng: () => number): number {
  return ageToF(sampleArrivalAge(cfg, rng), cfg.eta_ref);
}

function meanShrink(age: number, mix: number[], spreadScale: number): number {
  const mean = mix.reduce((s, a) => s + a, 0) / mix.length;
  return mean + spreadScale * (age - mean);
}

/** Discrete prior PMF on a uniform freshness grid (FIL-03-style teaching view). */
export function arrivalFreshnessPriorPdf(
  cfg: SimConfig,
  opts?: { transitBiasOverride?: number; nGrid?: number },
): { f: number; density: number }[] {
  const nGrid = opts?.nGrid ?? 81;
  const fMax = 1;
  const bias =
    opts?.transitBiasOverride !== undefined
      ? opts.transitBiasOverride
      : cfg.transit_temp_bias_c;
  const factor = Math.max(1.01, cfg.q10) ** (bias / 10);
  const mix = baseMixAges(cfg);
  const freshes = mix.map((a) =>
    ageToF(meanShrink(a, mix, cfg.spread_scale) * factor, cfg.eta_ref),
  );
  const bw = Math.max(0.015, cfg.spread_scale * 0.055);
  const dx = fMax / (nGrid - 1);
  const pts: { f: number; density: number }[] = [];
  for (let i = 0; i < nGrid; i++) {
    const f = i * dx;
    let dens = 0;
    for (const ff of freshes) {
      const z = (f - ff) / bw;
      dens += Math.exp(-0.5 * z * z);
    }
    dens /= freshes.length * bw * Math.sqrt(2 * Math.PI);
    pts.push({ f, density: dens });
  }
  let mass = 0;
  for (const p of pts) mass += p.density * dx;
  if (mass > 0) for (const p of pts) p.density /= mass;
  return pts;
}

/** @deprecated use arrivalFreshnessPriorPdf */
export function arrivalAgePriorPdf(
  cfg: SimConfig,
  opts?: { transitBiasOverride?: number; nGrid?: number },
): { f: number; density: number }[] {
  return arrivalFreshnessPriorPdf(cfg, opts);
}

/** F2a-style Gaussian centered on mix mean (pack-date prior width). */
export function f2aPriorPdf(
  cfg: SimConfig,
  nGrid = 81,
): { f: number; density: number }[] {
  const mix = baseMixAges(cfg);
  const ages = mix.map((a) => meanShrink(a, mix, cfg.spread_scale));
  const meanAge =
    (ages.reduce((s, a) => s + a, 0) / ages.length) * transitAgeFactor(cfg);
  const meanF = ageToF(meanAge, cfg.eta_ref);
  const ageMean = ages.reduce((s, a) => s + a, 0) / ages.length;
  const ageStd =
    ages.length > 1
      ? Math.sqrt(
          ages.reduce((s, a) => s + (a - ageMean) ** 2, 0) / ages.length,
        )
      : 0.75;
  const sd = Math.max(0.015, (ageStd * transitAgeFactor(cfg)) / cfg.eta_ref);
  const fMax = 1;
  const pts: { f: number; density: number }[] = [];
  const dx = fMax / (nGrid - 1);
  for (let i = 0; i < nGrid; i++) {
    const f = i * dx;
    const z = (f - meanF) / sd;
    pts.push({
      f,
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

/** Effective characteristic life under Q10 temperature shift (teaching display). */
export function etaEffective(cfg: SimConfig): number {
  const shift = (cfg.t_ref_c - cfg.t_store_c) / 10;
  return Math.max(0.5, cfg.eta_ref * cfg.q10 ** shift);
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

/** E[f]-weighted on-hand from truth lots (MVP policy parity). */
export function effectiveInventoryFromLots(lots: Lot[]): number {
  return lots.reduce((s, l) => s + l.n * l.mean_f, 0);
}

export function onHandInventory(lots: Lot[]): number {
  return totalInventory(lots);
}

function drawGammaDecrement(cfg: SimConfig, rng: () => number): number {
  const scale = GAMMA_SCALE * storeTempFactor(cfg);
  return sampleGamma(rng, GAMMA_SHAPE, scale);
}

/** Age one day; gamma freshness decrement draws waste from each unit. */
function ageAndSpoilUnits(
  units: Unit[],
  cfg: SimConfig,
  rng: () => number,
): { units: Unit[]; waste: number; exits: UnitExit[] } {
  let waste = 0;
  const next: Unit[] = [];
  const exits: UnitExit[] = [];
  for (const unit of units) {
    const decrement = drawGammaDecrement(cfg, rng);
    const fAfter = Math.max(0, unit.f - decrement);
    const p =
      unit.f <= 0
        ? 1
        : clamp((unit.f - fAfter) / unit.f, 0, 1);
    if (rng() >= p) {
      next.push({ ...unit, f: fAfter });
    } else {
      waste += 1;
      exits.push({
        unit_id: unit.unit_id,
        lot_id: unit.lot_id,
        f: unit.f,
        cause: "spoiled",
      });
    }
  }
  return { units: next, waste, exits };
}

function applySalesUnits(
  units: Unit[],
  demand: number,
): { units: Unit[]; sales: number; stockout: number; exits: UnitExit[] } {
  let remaining = demand;
  let sales = 0;
  const exits: UnitExit[] = [];
  const ordered = [...units].sort(
    (a, b) => b.f - a.f || a.lot_id - b.lot_id || a.unit_id - b.unit_id,
  );
  const keep = new Set<number>();
  for (const unit of ordered) {
    if (remaining <= 0) {
      keep.add(unit.unit_id);
      continue;
    }
    sales += 1;
    remaining -= 1;
    exits.push({
      unit_id: unit.unit_id,
      lot_id: unit.lot_id,
      f: unit.f,
      cause: "sold",
    });
  }
  return {
    units: units.filter((u) => keep.has(u.unit_id)),
    sales,
    stockout: remaining,
    exits,
  };
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

/** Approx Gamma(shape, scale) via Marsaglia-Tsang. */
function sampleGamma(rng: () => number, shape: number, scale: number): number {
  if (shape < 1) {
    const u = Math.max(1e-12, rng());
    return sampleGamma(rng, shape + 1, scale) * u ** (1 / shape);
  }
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
  // Decorative non-physics seasonal wobble (teaching stub; not calendar DOW).
  const seasonal = 1 + 0.18 * Math.sin(day / 3);
  const mu = Math.max(0.1, cfg.demand_mu * seasonal);
  const vm = Math.max(1.05, cfg.demand_vm);
  const r = mu / (vm - 1);
  const lam = sampleGamma(rng, r, mu / r);
  return samplePoisson(rng, lam);
}

function beliefBlur(scenario: ScenarioId): number {
  if (scenario === "P0") return 0.16;
  if (scenario === "F2") return 0.055;
  if (scenario === "F2a") return 0.07;
  if (scenario === "F1s") return 0.085;
  if (scenario === "F1") return 0.095;
  return 0.1; // P1
}

/**
 * Flat L×K f-wire belief from live lots (fake physics; projector rebins to heatmap).
 */
export function generateFlatBelief(
  lots: Lot[],
  rng: () => number,
  scenario: ObsScenarioKey = "P1",
  K = 12,
): FlatBelief {
  const L = lots.length;
  if (L === 0) {
    return {
      L: 0,
      K,
      lot_counts: [],
      f_marginals: [],
      f_grid: Array.from({ length: K }, (_, i) => (i + 0.5) / K),
    };
  }

  const lot_counts = lots.map((l) => l.n);
  const f_grid = Array.from(
    { length: K },
    (_, i) => i / Math.max(1, K - 1),
  );
  const blurF = beliefBlur(scenario === "custom" ? "P1" : scenario);
  const f_marginals: number[] = [];

  for (let l = 0; l < L; l++) {
    const fTruth = lots[l]!.mean_f;
    const row: number[] = [];
    let sum = 0;
    for (let k = 0; k < K; k++) {
      const d = (f_grid[k]! - fTruth) / Math.max(0.05, blurF);
      const mass = Math.exp(-(d * d) / 2) * (0.75 + 0.5 * rng());
      row.push(mass);
      sum += mass;
    }
    for (const m of row) {
      f_marginals.push(sum > 0 ? m / sum : 1 / K);
    }
  }

  return { L, K, lot_counts, f_marginals, f_grid };
}

export function generateBelief(
  lots: Lot[],
  rng: () => number,
  scenario: ScenarioId = "P1",
): BeliefGrid {
  const fBins = 12;
  const countBins = 10;
  const f_edges = Array.from({ length: fBins + 1 }, (_, i) => i / fBins);
  const maxCount = Math.max(40, totalInventory(lots) * 1.4);
  const count_edges = Array.from(
    { length: countBins + 1 },
    (_, i) => (i / countBins) * maxCount,
  );
  const blur = beliefBlur(scenario);

  const density: number[][] = Array.from({ length: fBins }, () =>
    Array.from({ length: countBins }, () => 0),
  );

  const byF = new Map<number, number>();
  for (const lot of lots) {
    byF.set(lot.mean_f, (byF.get(lot.mean_f) ?? 0) + lot.n);
  }

  for (let fi = 0; fi < fBins; fi++) {
    const fCenter = (f_edges[fi]! + f_edges[fi + 1]!) / 2;
    for (let ci = 0; ci < countBins; ci++) {
      const countCenter = (count_edges[ci]! + count_edges[ci + 1]!) / 2;
      let mass = 0.02 * blur;
      for (const [f, n] of byF) {
        const dF = (fCenter - f) / blur;
        const dN = (countCenter - n) / blur;
        mass += Math.exp(
          -(dF * dF) / 2.2 - (dN * dN) / (2 * (maxCount * 0.18) ** 2),
        );
      }
      mass *= 0.75 + 0.5 * rng();
      density[fi]![ci] = mass;
    }
  }

  let sum = 0;
  for (const row of density) for (const v of row) sum += v;
  if (sum > 0) {
    for (const row of density) {
      for (let i = 0; i < row.length; i++) row[i]! /= sum;
    }
  }

  return { f_edges, count_edges, density };
}

function runDay(
  day: number,
  units: Unit[],
  pendingOrders: { arriveOn: number; qty: number }[],
  nextLotId: number,
  nextUnitId: number,
  orderQty: number,
  cfg: SimConfig,
  rng: () => number,
  autopilot: boolean,
): {
  units: Unit[];
  pendingOrders: { arriveOn: number; qty: number }[];
  nextLotId: number;
  nextUnitId: number;
  record: Day;
} {
  let stateUnits = units;
  let nid = nextLotId;
  let uid = nextUnitId;
  let pending = [...pendingOrders];

  const arrivals = pending
    .filter((o) => o.arriveOn === day)
    .reduce((s, o) => s + o.qty, 0);
  pending = pending.filter((o) => o.arriveOn !== day);
  let f_at_receipt: number | null = null;
  if (arrivals > 0) {
    f_at_receipt = Math.round(sampleArrivalFreshness(cfg, rng) * 1000) / 1000;
    const born = birthUnitsForLot(nid++, arrivals, f_at_receipt, rng, uid);
    stateUnits = [...stateUnits, ...born.units];
    uid = born.nextUnitId;
  }

  const aged = ageAndSpoilUnits(stateUnits, cfg, rng);
  stateUnits = aged.units;
  const demand = sampleDemand(rng, cfg, day);
  const sold = applySalesUnits(stateUnits, demand);
  stateUnits = sold.units;
  const unitExits = [...aged.exits, ...sold.exits];

  const stateLots = aggregateLotsFromUnits(stateUnits);

  let order_qty = snapCases(Math.max(0, orderQty), cfg.case_size);
  if (autopilot) {
    const inv = totalInventory(stateLots);
    const target = snapCases(cfg.base_stock, cfg.case_size);
    order_qty = snapCases(
      clamp(target - inv, 0, target * 2),
      cfg.case_size,
    );
  }

  const orderWeekdays = new Set(
    scheduleFromConfig(cfg).order_weekdays,
  );
  // Monday=0 convention (day 1 == Monday), matching scheduleFromConfig /
  // EventsPane's isDeliveryDay — NOT a raw `day % 7`, which desynced actual
  // arrivals from the UI's own "delivery day" labels (T-151 bugfix).
  const episodeWd = (((day - 1) % 7) + 7) % 7;
  if (!orderWeekdays.has(episodeWd)) {
    order_qty = 0;
  }

  if (order_qty > 0) {
    pending.push({ arriveOn: day + Math.max(0, Math.round(cfg.lead_time)), qty: order_qty });
  }

  return {
    units: stateUnits,
    pendingOrders: pending,
    nextLotId: nid,
    nextUnitId: uid,
    record: {
      day,
      lots: stateLots.map((l) => ({ ...l })),
      units: stateUnits.map((u) => ({ ...u })),
      unit_exits: unitExits.map((e) => ({ ...e })),
      sales_total: sold.sales,
      waste_total: aged.waste,
      demand,
      order_qty,
      arrivals,
      stockout: sold.stockout,
      f_at_receipt,
    },
  };
}

export function createInitialState(cfg: SimConfig): SimState {
  const config: SimConfig = { ...cfg };
  const rng = mulberry32(config.seed);
  const lots: Lot[] = [];
  const units: Unit[] = [];
  const nextLotId = 1;
  const nextUnitId = 0;
  const pendingOrders: { arriveOn: number; qty: number }[] = [];
  const history: Day[] = [];

  return {
    day: 0,
    lots,
    units,
    nextLotId,
    nextUnitId,
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
): { state: SimState; dayRecord: Day; completedDay: number } {
  const config = { ...cfg };
  const completedDay = state.day;
  const stepped = runDay(
    completedDay,
    state.units,
    state.pendingOrders,
    state.nextLotId,
    state.nextUnitId,
    orderQtyRaw,
    config,
    state.rng,
    false,
  );

  const history = [...state.history, stepped.record];

  return {
    state: {
      day: state.day + 1,
      lots: aggregateLotsFromUnits(stepped.units),
      units: stepped.units,
      nextLotId: stepped.nextLotId,
      nextUnitId: stepped.nextUnitId,
      pendingOrders: stepped.pendingOrders,
      history,
      rng: state.rng,
      config,
    },
    dayRecord: stepped.record,
    completedDay,
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

import type { BeliefGrid, Day, Economics, Lot } from "../types";

const CASE_SIZE = 12;
const WINDOW_DAYS = 14;
const MAX_AGE = 10;
const LEAD_TIME = 1;

export type SimState = {
  day: number;
  lots: Lot[];
  nextLotId: number;
  pendingOrders: { arriveOn: number; qty: number }[];
  history: Day[];
  rng: () => number;
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

function snapCases(qty: number, caseSize: number): number {
  if (qty <= 0) return 0;
  return Math.round(qty / caseSize) * caseSize;
}

function totalInventory(lots: Lot[]): number {
  return lots.reduce((s, l) => s + l.n, 0);
}

/** Age lots one day; units past MAX_AGE spoil. */
function ageAndSpoil(lots: Lot[]): { lots: Lot[]; waste: number } {
  let waste = 0;
  const next: Lot[] = [];
  for (const lot of lots) {
    const tau = lot.tau + 1;
    if (tau > MAX_AGE) {
      waste += lot.n;
    } else {
      next.push({ ...lot, tau });
    }
  }
  return { lots: next, waste };
}

/** FIFO sales drawdown against demand. */
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

function sampleDemand(rng: () => number, mean: number): number {
  // Discrete-ish demand around a seasonal mean
  const noise = (rng() + rng() + rng() - 1.5) * 8;
  return Math.max(0, Math.round(mean + noise));
}

export function generateBelief(
  lots: Lot[],
  rng: () => number,
): BeliefGrid {
  const tauBins = 12;
  const countBins = 10;
  const tau_edges = Array.from({ length: tauBins + 1 }, (_, i) => i);
  const maxCount = Math.max(40, totalInventory(lots) * 1.4);
  const count_edges = Array.from(
    { length: countBins + 1 },
    (_, i) => (i / countBins) * maxCount,
  );

  // Truth mass from current lots, smeared into a soft KDE-like grid
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
      let mass = 0;
      for (const [tau, n] of byAge) {
        const dTau = tauCenter - tau;
        const dN = countCenter - n;
        mass += Math.exp(-(dTau * dTau) / 2.2 - (dN * dN) / (2 * (maxCount * 0.18) ** 2));
      }
      // Belief noise / prior blur
      mass *= 0.75 + 0.5 * rng();
      density[ti]![ci] = mass;
    }
  }

  // Normalize
  let sum = 0;
  for (const row of density) for (const v of row) sum += v;
  if (sum > 0) {
    for (const row of density) {
      for (let i = 0; i < row.length; i++) row[i]! /= sum;
    }
  }

  return { tau_edges, count_edges, density };
}

export function createInitialState(seed = 42): SimState {
  const rng = mulberry32(seed);
  const lots: Lot[] = [
    { lot_id: 1, n: 24, tau: 2 },
    { lot_id: 2, n: 36, tau: 4 },
    { lot_id: 3, n: 12, tau: 6 },
  ];
  let nextLotId = 4;
  const pendingOrders: { arriveOn: number; qty: number }[] = [];
  const history: Day[] = [];
  let day = 0;

  // Warm-start a rolling window of synthetic history
  let stateLots = lots;
  for (let i = 0; i < WINDOW_DAYS; i++) {
    day += 1;
    const arrivals = pendingOrders
      .filter((o) => o.arriveOn === day)
      .reduce((s, o) => s + o.qty, 0);
    // clear arrived
    for (let j = pendingOrders.length - 1; j >= 0; j--) {
      if (pendingOrders[j]!.arriveOn === day) pendingOrders.splice(j, 1);
    }
    if (arrivals > 0) {
      stateLots = [...stateLots, { lot_id: nextLotId++, n: arrivals, tau: 0 }];
    }

    const aged = ageAndSpoil(stateLots);
    stateLots = aged.lots;
    const demand = sampleDemand(rng, 28 + 6 * Math.sin(day / 3));
    const sold = applySales(stateLots, demand);
    stateLots = sold.lots;

    // Autopilot orders during warm-start
    const inv = totalInventory(stateLots);
    const target = 48;
    const order_qty = snapCases(clamp(target - inv, 0, 72), CASE_SIZE);
    if (order_qty > 0) {
      pendingOrders.push({ arriveOn: day + LEAD_TIME, qty: order_qty });
    }

    history.push({
      day,
      lots: stateLots.map((l) => ({ ...l })),
      sales_total: sold.sales,
      waste_total: aged.waste,
      demand,
      order_qty,
      arrivals,
      stockout: sold.stockout,
    });
  }

  return {
    day,
    lots: stateLots,
    nextLotId,
    pendingOrders,
    history,
    rng,
  };
}

export function stepSimulation(
  state: SimState,
  orderQtyRaw: number,
): { state: SimState; dayRecord: Day } {
  const order_qty = snapCases(Math.max(0, orderQtyRaw), CASE_SIZE);
  let { day, lots, nextLotId, pendingOrders, history, rng } = state;

  day += 1;

  const arrivals = pendingOrders
    .filter((o) => o.arriveOn === day)
    .reduce((s, o) => s + o.qty, 0);
  pendingOrders = pendingOrders.filter((o) => o.arriveOn !== day);
  if (arrivals > 0) {
    lots = [...lots, { lot_id: nextLotId++, n: arrivals, tau: 0 }];
  }

  const aged = ageAndSpoil(lots);
  lots = aged.lots;
  const demand = sampleDemand(rng, 28 + 6 * Math.sin(day / 3));
  const sold = applySales(lots, demand);
  lots = sold.lots;

  if (order_qty > 0) {
    pendingOrders = [
      ...pendingOrders,
      { arriveOn: day + LEAD_TIME, qty: order_qty },
    ];
  }

  const dayRecord: Day = {
    day,
    lots: lots.map((l) => ({ ...l })),
    sales_total: sold.sales,
    waste_total: aged.waste,
    demand,
    order_qty,
    arrivals,
    stockout: sold.stockout,
  };

  history = [...history, dayRecord].slice(-WINDOW_DAYS);

  return {
    state: {
      day,
      lots,
      nextLotId,
      pendingOrders,
      history,
      rng,
    },
    dayRecord,
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

export const MOCK_DEFAULTS = {
  CASE_SIZE,
  WINDOW_DAYS,
  MAX_AGE,
  LEAD_TIME,
  economics: {
    p_sell: 4.5,
    c_unit: 1.8,
    c_waste: 1.2,
    c_stockout: 2.5,
  } satisfies Economics,
};

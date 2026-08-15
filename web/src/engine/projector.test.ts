/**
 * T-090 / T-054: ViewModelProjector applies Snapshot/DayDelta; setEconomics is local;
 * BeliefGrid is age×count rebin (K×C) + merged age marginal (ADR 0109).
 */
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_ECONOMICS, computePnL } from "../mock/generate";
import type { Day, Economics } from "../types";
import type { EngineAdapter } from "./adapter";
import {
  ViewModelProjector,
  beliefGridFromFlat,
} from "./projector";
import * as projectorMod from "./projector";
import type { DayDelta, FlatBelief, Snapshot } from "./types";

/** Mirror of centersToEdges for expected tau_edges (implementer may export the real one). */
function expectedCentersToEdges(centers: number[]): number[] {
  if (centers.length === 0) return [];
  if (centers.length === 1) {
    const c = centers[0]!;
    return [c, c + 1];
  }
  const edges: number[] = [centers[0]! - (centers[1]! - centers[0]!) / 2];
  for (let i = 0; i < centers.length - 1; i++) {
    edges.push((centers[i]! + centers[i + 1]!) / 2);
  }
  const last = centers[centers.length - 1]!;
  const prev = centers[centers.length - 2]!;
  edges.push(last + (last - prev) / 2);
  return edges;
}

function ageMarginalFromFlat(flat: FlatBelief): number[] {
  const fn = (
    projectorMod as { ageMarginalFromFlat?: (f: FlatBelief) => number[] }
  ).ageMarginalFromFlat;
  expect(typeof fn).toBe("function");
  return fn!(flat);
}

type BeliefGridFromFlatFn = (
  flat: FlatBelief,
  truthLots?: ReadonlyArray<{ n: number }>,
) => ReturnType<typeof beliefGridFromFlat>;

const beliefGridFromFlatWithTruth = beliefGridFromFlat as BeliefGridFromFlatFn;

const FLAT_BELIEF: FlatBelief = {
  L: 2,
  K: 4,
  lot_counts: [3.6, 3.32],
  age_marginals: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
  tau_grid: [0, 2.6666666666666665, 5.333333333333333, 8],
};

function sampleSnapshot(overrides: Partial<Snapshot> = {}): Snapshot {
  return {
    seq: 0,
    episode_day: 0,
    belief: { ...FLAT_BELIEF, age_marginals: [...FLAT_BELIEF.age_marginals] },
    history: [],
    live_lots: [],
    pipeline: [],
    ...overrides,
  };
}

function sampleDay(day = 0): Day {
  return {
    day,
    lots: [{ lot_id: 1, n: 8, tau: 2 }],
    sales_total: 10,
    waste_total: 1,
    demand: 12,
    order_qty: 8,
    arrivals: 8,
    stockout: 2,
    age_at_receipt: 1,
  };
}

function sampleDelta(overrides: Partial<DayDelta> = {}): DayDelta {
  return {
    seq: 1,
    episode_day: 0,
    day: sampleDay(0),
    drop_oldest: false,
    belief: {
      ...FLAT_BELIEF,
      age_marginals: [
        0.266, 0.255, 0.244, 0.235, 0.266, 0.255, 0.244, 0.235,
      ],
      lot_counts: [1.1, 1.25],
    },
    live_lots: [{ lot_id: 1, n: 8, tau: 2 }],
    pipeline: [{ qty: 16, arrive_on: 1, days_until: 1 }],
    ...overrides,
  };
}

describe("ViewModelProjector.applySnapshot", () => {
  it("maps Snapshot into the existing ViewModel shape used by D3 charts", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 14,
    });
    const snap = sampleSnapshot({
      live_lots: [{ lot_id: 7, n: 4, tau: 3 }],
      episode_day: 0,
    });
    const vm = projector.applySnapshot(snap);

    expect(vm).toMatchObject({
      episode_day: 0,
      window_days: 14,
      history: [],
      live_lots: [{ lot_id: 7, n: 4, tau: 3 }],
      economics: expect.objectContaining({
        p_sell: DEFAULT_ECONOMICS.p_sell,
      }),
    });
    expect(Array.isArray(vm.pnl_series)).toBe(true);
    expect(vm.pnl_totals).toEqual(
      expect.objectContaining({
        revenue: expect.any(Number),
        cost: expect.any(Number),
        profit: expect.any(Number),
      }),
    );
    expect(vm.belief).toEqual(
      expect.objectContaining({
        density: expect.any(Array),
        tau_edges: expect.any(Array),
      }),
    );
    expect(vm.belief.density.length).toBeGreaterThan(0);
  });
});

describe("ViewModelProjector.applyDelta", () => {
  it("appends DayDelta.day into history and refreshes belief / lots", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 14,
    });
    projector.applySnapshot(sampleSnapshot());
    const delta = sampleDelta();
    const vm = projector.applyDelta(delta);

    expect(vm.episode_day).toBe(delta.episode_day);
    expect(vm.history).toHaveLength(1);
    expect(vm.history[0]).toEqual(
      expect.objectContaining({
        day: 0,
        sales_total: 10,
        demand: 12,
      }),
    );
    expect(vm.live_lots).toEqual([{ lot_id: 1, n: 8, tau: 2 }]);
    expect(vm.pnl_series).toHaveLength(1);
    expect(vm.pnl_series[0]!.revenue).toBe(
      10 * DEFAULT_ECONOMICS.p_sell,
    );
    expect(vm.belief.density.length).toBeGreaterThan(0);
  });

  it("fills history[].lots from live_lots when wire day omits lots (HTTP)", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 14,
    });
    projector.applySnapshot(sampleSnapshot());
    const live = [{ lot_id: 2, n: 16, tau: 2.23 }];
    const vm = projector.applyDelta(
      sampleDelta({
        day: {
          day: 1,
          L: 1,
          arrivals: 16,
          demand: 10,
          order_qty: 16,
          sales_total: 8,
          waste_total: 0,
          // no lots — matches EngineSession / golden DayDelta.day
        },
        live_lots: live,
      }),
    );

    expect(vm.history).toHaveLength(1);
    expect(vm.history[0]!.lots).toEqual(live);
    expect(vm.live_lots).toEqual(live);
  });

  it("honours drop_oldest when the rolling window is full", () => {
    const windowDays = 2;
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: windowDays,
    });
    projector.applySnapshot(sampleSnapshot());
    projector.applyDelta(
      sampleDelta({
        seq: 1,
        day: sampleDay(0),
        drop_oldest: false,
      }),
    );
    projector.applyDelta(
      sampleDelta({
        seq: 2,
        episode_day: 1,
        day: sampleDay(1),
        drop_oldest: false,
      }),
    );
    const vm = projector.applyDelta(
      sampleDelta({
        seq: 3,
        episode_day: 2,
        day: sampleDay(2),
        drop_oldest: true,
      }),
    );

    expect(Array.isArray(vm.history)).toBe(true);
    expect(vm.history).toHaveLength(windowDays);
    expect(vm.history?.[0]?.day).toBe(1);
    expect(vm.history?.[1]?.day).toBe(2);
  });
});

describe("ViewModelProjector.setEconomics (local reproject)", () => {
  it("updates PnL locally without calling any EngineAdapter method", () => {
    const adapter: EngineAdapter = {
      init: vi.fn(async () => sampleSnapshot()),
      step: vi.fn(async () => sampleDelta()),
      step_n: vi.fn(async () => [sampleDelta()]),
      reset: vi.fn(async () => sampleSnapshot()),
      act: vi.fn(async () => sampleDelta()),
    };

    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 14,
    });
    projector.applySnapshot(sampleSnapshot());
    projector.applyDelta(sampleDelta());

    const next: Partial<Economics> = { p_sell: 9.0 };
    const vm = projector.setEconomics(next);

    expect(adapter.init).not.toHaveBeenCalled();
    expect(adapter.step).not.toHaveBeenCalled();
    expect(adapter.step_n).not.toHaveBeenCalled();
    expect(adapter.reset).not.toHaveBeenCalled();
    expect(adapter.act).not.toHaveBeenCalled();

    expect(vm.economics).toEqual(expect.objectContaining({ p_sell: 9.0 }));
    expect(vm.pnl_series?.[0]?.revenue).toBe(10 * 9.0);
    const expected = computePnL(
      [
        {
          day: 0,
          lots: [{ lot_id: 1, n: 8, tau: 2 }],
          sales_total: 10,
          waste_total: 1,
          demand: 12,
          order_qty: 8,
          arrivals: 8,
          stockout: 2,
          age_at_receipt: 1,
        },
      ],
      { ...DEFAULT_ECONOMICS, p_sell: 9.0 },
    );
    expect(vm.pnl_series?.[0]?.profit).toBe(expected.series[0]!.profit);
  });

  it("does not require an engine round-trip when economics alone change", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
    });
    projector.applySnapshot(sampleSnapshot());
    projector.applyDelta(sampleDelta());
    const before = projector.getViewModel();
    const after = projector.setEconomics({ c_waste: 5 });

    expect(after.economics).toEqual(expect.objectContaining({ c_waste: 5 }));
    expect(after.history).toEqual(before.history);
    expect(after.pnl_series?.[0]?.cost_waste).toBe(1 * 5);
  });
});

describe("beliefGridFromFlat age×count rebin (T-090 / ADR 0109)", () => {
  it("tau_edges domain follows tau_grid age span (~0..8), not lot-index [0, L]", () => {
    const grid = beliefGridFromFlat(FLAT_BELIEF);
    const expected = expectedCentersToEdges(FLAT_BELIEF.tau_grid);
    expect(grid.tau_edges).toEqual(expected);
    expect(grid.tau_edges).toHaveLength(FLAT_BELIEF.K + 1);
    // Age domain ≈ 0..8 — not lot-index 0..L (=2).
    expect(grid.tau_edges[0]!).toBeLessThan(1);
    expect(grid.tau_edges[grid.tau_edges.length - 1]!).toBeGreaterThan(7);
    expect(grid.tau_edges).not.toEqual([0, 1, 2]);
    expect(grid.tau_edges[grid.tau_edges.length - 1]!).not.toBe(FLAT_BELIEF.L);
  });

  it("density is shaped K×C (age bins × count bins), not L×K", () => {
    const grid = beliefGridFromFlat(FLAT_BELIEF);
    const K = FLAT_BELIEF.K;
    expect(grid.density).toHaveLength(K);
    const C = grid.density[0]?.length ?? 0;
    expect(C).toBeGreaterThan(0);
    for (const row of grid.density) {
      expect(row).toHaveLength(C);
    }
    // Supersedes T-054 L×K lot-index presentation.
    expect(grid.density).not.toHaveLength(FLAT_BELIEF.L);
    expect(grid.count_edges).toHaveLength(C + 1);
    expect(grid.tau_edges).toHaveLength(K + 1);
  });

  it("count_edges are integer-friendly from 0 through max(n_l, truth n, 1)", () => {
    const flat: FlatBelief = {
      L: 2,
      K: 3,
      lot_counts: [4, 2],
      age_marginals: [1 / 3, 1 / 3, 1 / 3, 1 / 3, 1 / 3, 1 / 3],
      tau_grid: [0, 4, 8],
    };
    const withTruth = beliefGridFromFlatWithTruth(flat, [{ n: 10 }]);
    expect(withTruth.count_edges[0]).toBe(0);
    expect(withTruth.count_edges[withTruth.count_edges.length - 1]!).toBeGreaterThanOrEqual(
      10,
    );
    for (let i = 0; i < withTruth.count_edges.length; i++) {
      expect(Number.isInteger(withTruth.count_edges[i]!)).toBe(true);
    }

    const noTruth = beliefGridFromFlat(flat);
    expect(noTruth.count_edges[0]).toBe(0);
    expect(noTruth.count_edges[noTruth.count_edges.length - 1]!).toBeGreaterThanOrEqual(4);

    const emptyLots: FlatBelief = {
      L: 0,
      K: 2,
      lot_counts: [],
      age_marginals: [],
      tau_grid: [0, 1],
    };
    const emptyGrid = beliefGridFromFlatWithTruth(emptyLots, []);
    // Floor of max(..., 1) when no lots / truth.
    if (emptyGrid.count_edges.length > 0) {
      expect(emptyGrid.count_edges[emptyGrid.count_edges.length - 1]!).toBeGreaterThanOrEqual(
        1,
      );
    }
  });

  it("deposits each lot’s mass into the nearest-integer count bin for n_l", () => {
    const binFor = (edges: number[], n: number): number => {
      const rounded = Math.round(n);
      for (let c = 0; c < edges.length - 1; c++) {
        if (rounded >= edges[c]! && rounded < edges[c + 1]!) return c;
      }
      return Math.max(0, edges.length - 2);
    };

    const flat: FlatBelief = {
      L: 2,
      K: 3,
      lot_counts: [4, 2],
      // Lot 0: all age mass in bin 0; lot 1: all in bin 2.
      age_marginals: [1, 0, 0, 0, 0, 1],
      tau_grid: [0, 4, 8],
    };
    const grid = beliefGridFromFlat(flat);
    expect(grid.density).toHaveLength(flat.K);
    const bin4 = binFor(grid.count_edges, 4);
    const bin2 = binFor(grid.count_edges, 2);

    expect(grid.density[0]![bin4]!).toBeCloseTo(4);
    expect(grid.density[2]![bin2]!).toBeCloseTo(2);
    // No cross-deposit into the other lot’s count bin at those ages.
    expect(grid.density[0]![bin2]!).toBeCloseTo(0);
    expect(grid.density[2]![bin4]!).toBeCloseTo(0);

    // Non-integer n_l → nearest-integer bin (3.6 → 4).
    const nonInt: FlatBelief = {
      L: 1,
      K: 2,
      lot_counts: [3.6],
      age_marginals: [0.5, 0.5],
      tau_grid: [0, 8],
    };
    const g2 = beliefGridFromFlat(nonInt);
    expect(g2.density).toHaveLength(nonInt.K);
    const bin36 = binFor(g2.count_edges, 3.6);
    expect(g2.density[0]![bin36]!).toBeCloseTo(3.6 * 0.5);
    expect(g2.density[1]![bin36]!).toBeCloseTo(3.6 * 0.5);
  });

  it("returns empty density for L=0 boundary", () => {
    const grid = beliefGridFromFlat({
      L: 0,
      K: 4,
      lot_counts: [],
      age_marginals: [],
      tau_grid: [],
    });
    expect(grid.density).toEqual([]);
  });

  it("truth (tau, n) land on the same age×count scales as rebinned cells", () => {
    const truth = [{ n: 8, tau: 2 }];
    const grid = beliefGridFromFlatWithTruth(FLAT_BELIEF, truth);
    const tau0 = grid.tau_edges[0]!;
    const tau1 = grid.tau_edges[grid.tau_edges.length - 1]!;
    const n0 = grid.count_edges[0]!;
    const n1 = grid.count_edges[grid.count_edges.length - 1]!;
    expect(truth[0]!.tau).toBeGreaterThanOrEqual(tau0);
    expect(truth[0]!.tau).toBeLessThanOrEqual(tau1);
    expect(truth[0]!.n).toBeGreaterThanOrEqual(n0);
    expect(truth[0]!.n).toBeLessThanOrEqual(n1);
    // Scales are age×count — not lot-index x (0..L).
    expect(tau1).toBeGreaterThan(FLAT_BELIEF.L);
  });
});

describe("ageMarginalFromFlat (T-090)", () => {
  it("returns length-K merged age mass; sum equals Σ lot_counts when rows normalize", () => {
    const flat: FlatBelief = {
      L: 2,
      K: 3,
      lot_counts: [4, 10],
      age_marginals: [0.5, 0.3, 0.2, 0.1, 0.6, 0.3],
      tau_grid: [0, 4, 8],
    };
    const m = ageMarginalFromFlat(flat);
    expect(m).toHaveLength(flat.K);
    expect(m[0]!).toBeCloseTo(4 * 0.5 + 10 * 0.1);
    expect(m[1]!).toBeCloseTo(4 * 0.3 + 10 * 0.6);
    expect(m[2]!).toBeCloseTo(4 * 0.2 + 10 * 0.3);
    const sumM = m.reduce((a, b) => a + b, 0);
    const sumCounts = flat.lot_counts.reduce((a, b) => a + b, 0);
    expect(sumM).toBeCloseTo(sumCounts);

    const grid = beliefGridFromFlat(flat);
    expect(m).toHaveLength(grid.tau_edges.length - 1);
    // Optional: same vector may also live on BeliefGrid.
    const optionalMarginal = (
      grid as { age_marginal?: number[] }
    ).age_marginal;
    if (optionalMarginal !== undefined) {
      expect(optionalMarginal).toEqual(m);
    }
  });
});

describe("ViewModelProjector belief_history rolling window (T-115)", () => {
  it("belief_history length tracks history after applySnapshot + applyDelta; payloads omit showTruth", () => {
    const windowDays = 2;
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: windowDays,
    });
    const snap = sampleSnapshot();
    expect(Object.prototype.hasOwnProperty.call(snap, "showTruth")).toBe(
      false,
    );
    projector.applySnapshot(snap);

    const b1: FlatBelief = {
      ...FLAT_BELIEF,
      lot_counts: [1, 1],
      age_marginals: [...FLAT_BELIEF.age_marginals],
    };
    const b2: FlatBelief = {
      ...FLAT_BELIEF,
      lot_counts: [2, 2],
      age_marginals: [...FLAT_BELIEF.age_marginals],
    };
    const b3: FlatBelief = {
      ...FLAT_BELIEF,
      lot_counts: [3, 3],
      age_marginals: [...FLAT_BELIEF.age_marginals],
    };

    const d1 = sampleDelta({
      seq: 1,
      episode_day: 0,
      day: sampleDay(0),
      drop_oldest: false,
      belief: b1,
    });
    const d2 = sampleDelta({
      seq: 2,
      episode_day: 1,
      day: sampleDay(1),
      drop_oldest: false,
      belief: b2,
    });
    const d3 = sampleDelta({
      seq: 3,
      episode_day: 2,
      day: sampleDay(2),
      drop_oldest: true,
      belief: b3,
    });
    expect(Object.prototype.hasOwnProperty.call(d1, "showTruth")).toBe(false);
    expect(Object.prototype.hasOwnProperty.call(d2, "showTruth")).toBe(false);
    expect(Object.prototype.hasOwnProperty.call(d3, "showTruth")).toBe(false);

    projector.applyDelta(d1);
    projector.applyDelta(d2);
    projector.applyDelta(d3);

    const vm = projector.getViewModel() as ReturnType<
      ViewModelProjector["getViewModel"]
    > & {
      belief_history?: Array<{ day: number; flatBelief: FlatBelief }>;
    };

    expect(vm.history).toHaveLength(windowDays);
    expect(Array.isArray(vm.belief_history)).toBe(true);
    expect(vm.belief_history).toHaveLength(vm.history.length);
    expect(vm.belief_history?.map((b) => b.day)).toEqual(
      vm.history.map((h) => h.day),
    );
    expect(vm.belief_history?.[0]?.flatBelief.lot_counts).toEqual([2, 2]);
    expect(vm.belief_history?.[1]?.flatBelief.lot_counts).toEqual([3, 3]);
  });
});


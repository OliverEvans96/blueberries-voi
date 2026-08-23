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
  stockoutFromDayFields,
} from "./projector";
import * as projectorMod from "./projector";
import type { DayDelta, FlatBelief, Snapshot } from "./types";

/** Mirror of centersToEdges for expected f_edges (implementer may export the real one). */
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

function fMarginalFromFlat(flat: FlatBelief): number[] {
  const fn = (
    projectorMod as { fMarginalFromFlat?: (f: FlatBelief) => number[] }
  ).fMarginalFromFlat;
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
  f_marginals: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
  f_grid: [0.125, 0.375, 0.625, 0.875],
};

function sampleSnapshot(overrides: Partial<Snapshot> = {}): Snapshot {
  return {
    seq: 0,
    episode_day: 0,
    belief: { ...FLAT_BELIEF, f_marginals: [...FLAT_BELIEF.f_marginals] },
    history: [],
    live_lots: [],
    pipeline: [],
    ...overrides,
  };
}

function sampleDay(day = 0): Day {
  return {
    day,
    lots: [{ lot_id: 1, n: 8, mean_f: 0.857 }],
    sales_total: 10,
    waste_total: 1,
    demand: 12,
    order_qty: 8,
    arrivals: 8,
    stockout: 2,
    f_at_receipt: 1,
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
      f_marginals: [
        0.266, 0.255, 0.244, 0.235, 0.266, 0.255, 0.244, 0.235,
      ],
      lot_counts: [1.1, 1.25],
    },
    live_lots: [{ lot_id: 1, n: 8, mean_f: 0.857 }],
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
      live_lots: [{ lot_id: 7, n: 4, mean_f: 0.786 }],
      episode_day: 0,
    });
    const vm = projector.applySnapshot(snap);

    expect(vm).toMatchObject({
      episode_day: 0,
      window_days: 14,
      history: [],
      live_lots: [{ lot_id: 7, n: 4, mean_f: 0.786 }],
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
        f_edges: expect.any(Array),
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
    expect(vm.live_lots).toEqual([{ lot_id: 1, n: 8, mean_f: 0.857 }]);
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
    const live = [{ lot_id: 2, n: 16, mean_f: 0.841 }];
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

  it("fills history[].units from live_units when wire day omits units (HTTP)", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 14,
    });
    projector.applySnapshot(sampleSnapshot());
    const liveUnits = [
      { unit_id: 0, lot_id: 2, f: 0.91 },
      { unit_id: 1, lot_id: 2, f: 0.88 },
    ];
    const vm = projector.applyDelta(
      sampleDelta({
        day: {
          day: 1,
          L: 2,
          arrivals: 16,
          demand: 10,
          order_qty: 16,
          sales_total: 8,
          waste_total: 0,
        },
        live_lots: [{ lot_id: 2, n: 2, mean_f: 0.895 }],
        live_units: liveUnits,
      }),
    );

    expect(vm.history).toHaveLength(1);
    expect(vm.history[0]!.units).toEqual(liveUnits);
    expect(vm.live_units).toEqual(liveUnits);
  });

  it("never drops history for drop_oldest true or a 14-day window_days cap (T-112)", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 14,
    });
    projector.applySnapshot(sampleSnapshot());
    for (let i = 0; i < 16; i++) {
      projector.applyDelta(
        sampleDelta({
          seq: i + 1,
          episode_day: i,
          day: sampleDay(i),
          drop_oldest: i >= 14,
        }),
      );
    }
    const vm = projector.getViewModel();
    expect(vm.history).toHaveLength(16);
    expect(vm.history[0]?.day).toBe(0);
    expect(vm.history[15]?.day).toBe(15);
    expect(vm.pnl_series).toHaveLength(16);
    const expectedRevenue = 16 * 10 * DEFAULT_ECONOMICS.p_sell;
    expect(vm.pnl_totals.revenue).toBeCloseTo(expectedRevenue);
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
          lots: [{ lot_id: 1, n: 8, mean_f: 0.857 }],
          sales_total: 10,
          waste_total: 1,
          demand: 12,
          order_qty: 8,
          arrivals: 8,
          stockout: 2,
          f_at_receipt: 1,
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
  it("f_edges domain follows tau_grid age span (~0..8), not lot-index [0, L]", () => {
    const grid = beliefGridFromFlat(FLAT_BELIEF);
    const expected = expectedCentersToEdges(FLAT_BELIEF.f_grid);
    expect(grid.f_edges).toEqual(expected);
    expect(grid.f_edges).toHaveLength(FLAT_BELIEF.K + 1);
    // Freshness domain in [0,1] — not lot-index 0..L (=2).
    expect(grid.f_edges[0]!).toBeGreaterThanOrEqual(0);
    expect(grid.f_edges[grid.f_edges.length - 1]!).toBeLessThanOrEqual(1);
    expect(grid.f_edges).not.toEqual([0, 1, 2]);
    expect(grid.f_edges[grid.f_edges.length - 1]!).not.toBe(FLAT_BELIEF.L);
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
    expect(grid.f_edges).toHaveLength(K + 1);
  });

  it("count_edges are integer-friendly from 0 through max(n_l, truth n, 1)", () => {
    const flat: FlatBelief = {
      L: 2,
      K: 3,
      lot_counts: [4, 2],
      f_marginals: [1 / 3, 1 / 3, 1 / 3, 1 / 3, 1 / 3, 1 / 3],
      f_grid: [0.167, 0.5, 0.833],
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
      f_marginals: [],
      f_grid: [0.25, 0.75],
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
      f_marginals: [1, 0, 0, 0, 0, 1],
      f_grid: [0.167, 0.5, 0.833],
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
      f_marginals: [0.5, 0.5],
      f_grid: [0, 1],
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
      f_marginals: [],
      f_grid: [],
    });
    expect(grid.density).toEqual([]);
  });

  it("truth (mean_f, n) land on the same freshness×count scales as rebinned cells", () => {
    const truth = [{ n: 8, mean_f: 0.857 }];
    const grid = beliefGridFromFlatWithTruth(FLAT_BELIEF, truth);
    const f0 = grid.f_edges[0]!;
    const f1 = grid.f_edges[grid.f_edges.length - 1]!;
    const n0 = grid.count_edges[0]!;
    const n1 = grid.count_edges[grid.count_edges.length - 1]!;
    expect(truth[0]!.mean_f).toBeGreaterThanOrEqual(f0);
    expect(truth[0]!.mean_f).toBeLessThanOrEqual(f1);
    expect(truth[0]!.n).toBeGreaterThanOrEqual(n0);
    expect(truth[0]!.n).toBeLessThanOrEqual(n1);
    // Scales are age×count — not lot-index x (0..L).
    expect(f1).toBeLessThanOrEqual(1);
  });
});

describe("fMarginalFromFlat (T-090)", () => {
  it("returns length-K merged f mass; sum equals Σ lot_counts when rows normalize", () => {
    const flat: FlatBelief = {
      L: 2,
      K: 3,
      lot_counts: [4, 10],
      f_marginals: [0.5, 0.3, 0.2, 0.1, 0.6, 0.3],
      f_grid: [0.167, 0.5, 0.833],
    };
    const m = fMarginalFromFlat(flat);
    expect(m).toHaveLength(flat.K);
    expect(m[0]!).toBeCloseTo(4 * 0.5 + 10 * 0.1);
    expect(m[1]!).toBeCloseTo(4 * 0.3 + 10 * 0.6);
    expect(m[2]!).toBeCloseTo(4 * 0.2 + 10 * 0.3);
    const sumM = m.reduce((a, b) => a + b, 0);
    const sumCounts = flat.lot_counts.reduce((a, b) => a + b, 0);
    expect(sumM).toBeCloseTo(sumCounts);

    const grid = beliefGridFromFlat(flat);
    expect(m).toHaveLength(grid.f_edges.length - 1);
    // Optional: same vector may also live on BeliefGrid.
    const optionalMarginal = (
      grid as { f_marginal?: number[] }
    ).f_marginal;
    if (optionalMarginal !== undefined) {
      expect(optionalMarginal).toEqual(m);
    }
  });
});

describe("beliefFreshnessSeries (T-127)", () => {
  it("maps belief_history to per-day f_edges and merged marginals", () => {
    const fn = (
      projectorMod as {
        beliefFreshnessSeries?: (
          bh: Array<{ day: number; flatBelief: FlatBelief }>,
        ) => Array<{ day: number; f_edges: number[]; marginal: number[] }>;
      }
    ).beliefFreshnessSeries;
    expect(typeof fn).toBe("function");
    const flat: FlatBelief = {
      L: 2,
      K: 3,
      lot_counts: [4, 10],
      f_marginals: [0.5, 0.3, 0.2, 0.1, 0.6, 0.3],
      f_grid: [0.167, 0.5, 0.833],
    };
    const series = fn!([
      { day: 0, flatBelief: flat },
      { day: 1, flatBelief: { ...flat, lot_counts: [5, 11] } },
    ]);
    expect(series).toHaveLength(2);
    expect(series[0]!.day).toBe(0);
    expect(series[0]!.marginal).toEqual(fMarginalFromFlat(flat));
    expect(series[0]!.f_edges).toEqual(expectedCentersToEdges(flat.f_grid));
    expect(series[1]!.marginal).toEqual(
      fMarginalFromFlat({ ...flat, lot_counts: [5, 11] }),
    );
  });
});

describe("ViewModelProjector belief_history rolling window (T-115)", () => {
  it("belief_history length tracks history after applySnapshot + applyDelta; payloads omit showTruth", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: 2,
    });
    const snap = sampleSnapshot();
    expect(Object.prototype.hasOwnProperty.call(snap, "showTruth")).toBe(
      false,
    );
    projector.applySnapshot(snap);

    const b1: FlatBelief = {
      ...FLAT_BELIEF,
      lot_counts: [1, 1],
      f_marginals: [...FLAT_BELIEF.f_marginals],
    };
    const b2: FlatBelief = {
      ...FLAT_BELIEF,
      lot_counts: [2, 2],
      f_marginals: [...FLAT_BELIEF.f_marginals],
    };
    const b3: FlatBelief = {
      ...FLAT_BELIEF,
      lot_counts: [3, 3],
      f_marginals: [...FLAT_BELIEF.f_marginals],
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

    expect(vm.history).toHaveLength(3);
    expect(Array.isArray(vm.belief_history)).toBe(true);
    expect(vm.belief_history).toHaveLength(vm.history.length);
    expect(vm.belief_history?.map((b) => b.day)).toEqual(
      vm.history.map((h) => h.day),
    );
    expect(vm.belief_history?.[0]?.flatBelief.lot_counts).toEqual([1, 1]);
    expect(vm.belief_history?.[1]?.flatBelief.lot_counts).toEqual([2, 2]);
    expect(vm.belief_history?.[2]?.flatBelief.lot_counts).toEqual([3, 3]);
  });
});

describe("ViewModelProjector heatmap density from snapshot.belief (T-117)", () => {
  const peakedBelief = (ageBin: number): FlatBelief => {
    const K = 4;
    const f_marginals = Array.from({ length: 2 * K }, () => 0);
    f_marginals[ageBin] = 1;
    f_marginals[K + ageBin] = 1;
    return {
      L: 2,
      K,
      lot_counts: [5, 5],
      f_marginals,
      f_grid: [0.125, 0.375, 0.625, 0.875],
    };
  };

  function ageMass(density: number[][]): number[] {
    return density.map((row) => row.reduce((a, b) => a + b, 0));
  }

  it("applySnapshot density follows belief, not live_lots n/τ", () => {
    const projector = new ViewModelProjector();
    const belief = peakedBelief(0);
    const vm = projector.applySnapshot(
      sampleSnapshot({
        belief,
        live_lots: [{ lot_id: 1, n: 99, mean_f: 0.429 }],
      }),
    );
    const mass = ageMass(vm.belief.density);
    const sum = mass.reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(10);
    expect(mass[0]!).toBeCloseTo(10);
    expect(mass[3]!).toBeCloseTo(0);
    expect(vm.belief.f_marginal).toEqual(fMarginalFromFlat(belief));
  });

  it("patchEngineState: changing belief with fixed live_lots changes density", () => {
    const projector = new ViewModelProjector();
    const lots = [{ lot_id: 1, n: 8, mean_f: 0.857 }];
    projector.applySnapshot(
      sampleSnapshot({
        belief: peakedBelief(0),
        live_lots: lots,
      }),
    );
    const before = projector.getViewModel().belief.density.map((r) => [...r]);
    const vm = projector.patchEngineState({
      belief: peakedBelief(3),
      live_lots: lots,
      pipeline: [],
      episode_day: 0,
    });
    const afterMass = ageMass(vm.belief.density);
    const beforeMass = ageMass(before);
    expect(afterMass[3]!).toBeCloseTo(10);
    expect(beforeMass[0]!).toBeCloseTo(10);
    expect(afterMass).not.toEqual(beforeMass);
  });

  it("patchEngineState: changing live_lots with fixed belief does not rewrite age mass", () => {
    const projector = new ViewModelProjector();
    const belief = peakedBelief(1);
    projector.applySnapshot(
      sampleSnapshot({
        belief,
        live_lots: [{ lot_id: 1, n: 4, mean_f: 0.929 }],
      }),
    );
    const before = projector.getViewModel();
    const beforeMass = ageMass(before.belief.density);
    const vm = projector.patchEngineState({
      belief,
      live_lots: [
        { lot_id: 1, n: 4, mean_f: 0.929 },
        { lot_id: 2, n: 40, mean_f: 0.429 },
      ],
      pipeline: [],
      episode_day: 0,
    });
    const afterMass = ageMass(vm.belief.density);
    expect(afterMass).toEqual(beforeMass);
    expect(vm.belief.f_marginal).toEqual(before.belief.f_marginal);
    expect(vm.belief.count_edges.length).toBeGreaterThanOrEqual(
      before.belief.count_edges.length,
    );
  });

  it("patchEngineState after deltas: preserves history (wasm empty-history snapshot)", () => {
    const projector = new ViewModelProjector();
    projector.applySnapshot(
      sampleSnapshot({
        belief: peakedBelief(0),
        live_lots: [{ lot_id: 1, n: 8, mean_f: 0.857 }],
      }),
    );
    projector.applyDelta(
      sampleDelta({
        seq: 1,
        episode_day: 1,
        day: sampleDay(0),
        belief: peakedBelief(0),
      }),
    );
    projector.applyDelta(
      sampleDelta({
        seq: 2,
        episode_day: 2,
        day: sampleDay(1),
        belief: peakedBelief(1),
      }),
    );
    const before = projector.getViewModel();
    expect(before.history).toHaveLength(2);

    // Mimic wasm set_obs_scenario: real belief, empty history omitted from patch.
    const vm = projector.patchEngineState({
      belief: peakedBelief(3),
      live_lots: [{ lot_id: 1, n: 8, mean_f: 0.857 }],
      pipeline: [],
      episode_day: 2,
    });

    expect(vm.history).toHaveLength(2);
    expect(vm.history.map((d) => d.day)).toEqual(before.history.map((d) => d.day));
    expect(vm.episode_day).toBe(2);
    expect(ageMass(vm.belief.density)[3]!).toBeCloseTo(10);
    expect(vm.belief_history).toHaveLength(2);
    // Without belief_history wire, only the last day is patched (legacy path).
    expect(vm.belief_history[1]!.flatBelief.f_marginals[3]).toBe(1);
    expect(vm.belief_history[0]!.flatBelief.f_marginals[0]).toBe(1);
  });

  it("patchEngineState with belief_history replays all days for charts", () => {
    const projector = new ViewModelProjector();
    projector.applySnapshot(
      sampleSnapshot({
        belief: peakedBelief(0),
        live_lots: [{ lot_id: 1, n: 8, mean_f: 0.857 }],
      }),
    );
    projector.applyDelta(
      sampleDelta({
        seq: 1,
        episode_day: 1,
        day: sampleDay(0),
        belief: peakedBelief(0),
      }),
    );
    projector.applyDelta(
      sampleDelta({
        seq: 2,
        episode_day: 2,
        day: sampleDay(1),
        belief: peakedBelief(1),
      }),
    );

    const vm = projector.patchEngineState({
      belief: peakedBelief(3),
      belief_history: [
        { day: 0, belief: peakedBelief(2) },
        { day: 1, belief: peakedBelief(3) },
      ],
      live_lots: [{ lot_id: 1, n: 8, mean_f: 0.857 }],
      pipeline: [],
      episode_day: 2,
    });

    expect(vm.belief_history[0]!.flatBelief.f_marginals[2]).toBe(1);
    expect(vm.belief_history[1]!.flatBelief.f_marginals[3]).toBe(1);
  });

  it("applySnapshot uses wire belief_history when present", () => {
    const projector = new ViewModelProjector();
    const vm = projector.applySnapshot(
      sampleSnapshot({
        belief: peakedBelief(3),
        belief_history: [
          { day: 0, belief: peakedBelief(1) },
          { day: 1, belief: peakedBelief(2) },
        ],
        history: [sampleDay(0), sampleDay(1)],
        episode_day: 2,
      }),
    );
    expect(vm.belief_history[0]!.flatBelief.f_marginals[1]).toBe(1);
    expect(vm.belief_history[1]!.flatBelief.f_marginals[2]).toBe(1);
    expect(vm.belief_history).toHaveLength(2);
  });

  it("patchEngineState appends belief_history days missing from projector", () => {
    const projector = new ViewModelProjector();
    projector.applySnapshot(sampleSnapshot({ belief: peakedBelief(0) }));
    const vm = projector.patchEngineState({
      belief: peakedBelief(4),
      belief_history: [{ day: 5, belief: peakedBelief(5) }],
      episode_day: 6,
    });
    expect(vm.belief_history.some((b) => b.day === 5)).toBe(true);
    expect(vm.belief_history.find((b) => b.day === 5)!.flatBelief.f_marginals[5]).toBe(1);
  });

  it("patchEngineState skips belief_history update for empty stub belief", () => {
    const projector = new ViewModelProjector();
    projector.applySnapshot(
      sampleSnapshot({
        belief: peakedBelief(0),
        live_lots: [{ lot_id: 1, n: 8, mean_f: 0.857 }],
      }),
    );
    projector.applyDelta(
      sampleDelta({
        seq: 1,
        episode_day: 1,
        day: sampleDay(0),
        belief: peakedBelief(0),
      }),
    );
    const beforeCounts = projector
      .getViewModel()
      .belief_history.map((b) => [...b.flatBelief.lot_counts]);

    projector.patchEngineState({
      belief: {
        L: 0,
        K: 0,
        lot_counts: [],
        f_marginals: [],
        f_grid: [],
      },
      live_lots: [],
      pipeline: [],
      episode_day: 1,
    });

    const after = projector.getViewModel();
    expect(after.history).toHaveLength(1);
    expect(after.belief_history.map((b) => b.flatBelief.lot_counts)).toEqual(
      beforeCounts,
    );
  });
});

describe("stockoutFromDayFields (missed sales wire gap)", () => {
  it("derives max(0, demand - sales) when stockout is omitted", () => {
    expect(stockoutFromDayFields(12, 10)).toBe(2);
    expect(stockoutFromDayFields(8, 8)).toBe(0);
  });

  it("explicit stockout wins over derived value", () => {
    expect(stockoutFromDayFields(12, 10, 5)).toBe(5);
    expect(stockoutFromDayFields(12, 10, 0)).toBe(0);
  });

  it("demand < sales yields stockout 0", () => {
    expect(stockoutFromDayFields(8, 12)).toBe(0);
  });

  it("applyDelta without stockout derives missed sales for chart + PnL", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS, c_stockout: 3 },
      window_days: 14,
    });
    projector.applySnapshot(sampleSnapshot());
    const vm = projector.applyDelta(
      sampleDelta({
        day: {
          day: 0,
          sales_total: 10,
          waste_total: 0,
          demand: 15,
          order_qty: 8,
          arrivals: 0,
          lots: [{ lot_id: 1, n: 8, mean_f: 0.857 }],
        },
      }),
    );

    expect(vm.history[0]!.stockout).toBe(5);
    expect(vm.pnl_series[0]!.cost_stockout).toBe(5 * 3);
  });

  it("applySnapshot hydrates history stockout from demand and sales", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
    });
    const vm = projector.applySnapshot(
      sampleSnapshot({
        history: [
          {
            day: 0,
            lots: [],
            sales_total: 7,
            waste_total: 0,
            demand: 10,
            order_qty: 0,
            arrivals: 0,
            stockout: undefined as unknown as number,
            f_at_receipt: null,
          },
        ],
      }),
    );

    expect(vm.history[0]!.stockout).toBe(3);
  });
});

/** f-native wire (T-C2-A): FlatBelief carries f_grid / f_marginals, not τ fields. */
type FNativeFlatBelief = {
  L: number;
  K: number;
  lot_counts: number[];
  f_grid: number[];
  /** Row-major L×K alive-only normalized marginals. */
  f_marginals: number[];
};

function fNativeFlat(
  overrides: Partial<FNativeFlatBelief> & Pick<FNativeFlatBelief, "L" | "K">,
): FNativeFlatBelief {
  const { L, K } = overrides;
  return {
    L,
    K,
    lot_counts: overrides.lot_counts ?? Array.from({ length: L }, () => 1),
    f_grid:
      overrides.f_grid ??
      Array.from({ length: K }, (_, k) => (k + 0.5) / K),
    f_marginals:
      overrides.f_marginals ??
      Array.from({ length: L * K }, () => 1 / K),
    ...overrides,
  };
}

function asFWireBelief(flat: FNativeFlatBelief): FlatBelief {
  return flat as unknown as FlatBelief;
}

function freshnessEdgesFromGrid(
  grid: ReturnType<typeof beliefGridFromFlat>,
): number[] {
  const g = grid as ReturnType<typeof beliefGridFromFlat> & {
    f_edges?: number[];
    freshness_edges?: number[];
  };
  return g.f_edges ?? g.freshness_edges ?? grid.f_edges;
}

function fMarginalFromFNativeFlat(flat: FNativeFlatBelief): number[] {
  const fn = (
    projectorMod as { fMarginalFromFlat?: (f: FlatBelief) => number[] }
  ).fMarginalFromFlat;
  expect(typeof fn).toBe("function");
  return fn!(asFWireBelief(flat));
}

describe("beliefGridFromFlat f_grid / f_marginals (T-C2-A / AC-frontend)", () => {
  it("maps f_grid bin centers to freshness edges in [0, 1], not τ-day span", () => {
    const flat = fNativeFlat({
      L: 2,
      K: 4,
      lot_counts: [3.6, 3.32],
      f_grid: [0.125, 0.375, 0.625, 0.875],
      f_marginals: [1, 0, 0, 0, 0, 0, 0, 1],
    });
    const grid = beliefGridFromFlat(asFWireBelief(flat));
    const edges = freshnessEdgesFromGrid(grid);
    expect(edges).toHaveLength(flat.K + 1);
    expect(edges[0]!).toBeGreaterThanOrEqual(0);
    expect(edges[edges.length - 1]!).toBeLessThanOrEqual(1);
    // Freshness domain — not legacy τ_grid ≈ 0..8 days.
    expect(edges[edges.length - 1]!).toBeLessThan(2);
    expect(edges).not.toEqual(expectedCentersToEdges([0, 2.67, 5.33, 8]));
  });

  it("deposits lot mass from f_marginals row-major L×K", () => {
    const flat = fNativeFlat({
      L: 2,
      K: 3,
      lot_counts: [4, 2],
      f_grid: [0.1, 0.5, 0.9],
      // Lot 0 → bin 0; lot 1 → bin 2.
      f_marginals: [1, 0, 0, 0, 0, 1],
    });
    const grid = beliefGridFromFlat(asFWireBelief(flat));
    expect(grid.density).toHaveLength(flat.K);
    const bin4 = Math.round(4);
    const bin2 = Math.round(2);
    const c4 = grid.count_edges.findIndex((e) => e === bin4);
    const c2 = grid.count_edges.findIndex((e) => e === bin2);
    expect(c4).toBeGreaterThanOrEqual(0);
    expect(c2).toBeGreaterThanOrEqual(0);
    expect(grid.density[0]![c4]!).toBeCloseTo(4);
    expect(grid.density[2]![c2]!).toBeCloseTo(2);
    expect(grid.density[0]![c2]!).toBeCloseTo(0);
    expect(grid.density[2]![c4]!).toBeCloseTo(0);
  });

  it("returns empty density for L=0 f-native boundary", () => {
    const grid = beliefGridFromFlat(
      asFWireBelief({
        L: 0,
        K: 4,
        lot_counts: [],
        f_grid: [0.25, 0.5, 0.75, 1],
        f_marginals: [],
      }),
    );
    expect(grid.density).toEqual([]);
  });

  it("exposes Freshness × count heatmap axis labels", () => {
    const fn = (
      projectorMod as {
        beliefHeatmapAxisLabels?: () => { x: string; y: string };
      }
    ).beliefHeatmapAxisLabels;
    expect(typeof fn).toBe("function");
    const labels = fn!();
    expect(labels.x.toLowerCase()).toContain("freshness");
    expect(labels.y.toLowerCase()).toContain("count");
    expect(labels.x.toLowerCase()).not.toContain("age");
  });
});

describe("fMarginalFromFlat (T-C2-A / AC-frontend)", () => {
  it("merges per-lot f mass: m[k] = Σ_l lot_counts[l] × f_marginals[l×K+k]", () => {
    const flat = fNativeFlat({
      L: 2,
      K: 3,
      lot_counts: [4, 10],
      f_grid: [0.2, 0.5, 0.8],
      f_marginals: [0.5, 0.3, 0.2, 0.1, 0.6, 0.3],
    });
    const m = fMarginalFromFNativeFlat(flat);
    expect(m).toHaveLength(flat.K);
    expect(m[0]!).toBeCloseTo(4 * 0.5 + 10 * 0.1);
    expect(m[1]!).toBeCloseTo(4 * 0.3 + 10 * 0.6);
    expect(m[2]!).toBeCloseTo(4 * 0.2 + 10 * 0.3);
    const sumM = m.reduce((a, b) => a + b, 0);
    const sumCounts = flat.lot_counts.reduce((a, b) => a + b, 0);
    expect(sumM).toBeCloseTo(sumCounts);
  });
});


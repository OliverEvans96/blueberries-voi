/**
 * T-054 RED: ViewModelProjector applies Snapshot/DayDelta; setEconomics is local;
 * heatmap density from flat belief × lot counts.
 */
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_ECONOMICS, computePnL } from "../mock/generate";
import type { Day, Economics } from "../types";
import type { EngineAdapter } from "./adapter";
import {
  ViewModelProjector,
  densityFromFlatBelief,
} from "./projector";
import type { DayDelta, FlatBelief, Snapshot } from "./types";

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

describe("densityFromFlatBelief", () => {
  it("computes nested heatmap density as lot_counts × age_marginals (L×K)", () => {
    const belief: FlatBelief = {
      L: 2,
      K: 3,
      lot_counts: [4, 10],
      age_marginals: [0.5, 0.3, 0.2, 0.1, 0.6, 0.3],
      tau_grid: [0, 1, 2],
    };
    const density = densityFromFlatBelief(belief);

    expect(density).toHaveLength(2);
    expect(density[0]).toHaveLength(3);
    expect(density[1]).toHaveLength(3);
    expect(density[0]![0]).toBeCloseTo(4 * 0.5);
    expect(density[0]![1]).toBeCloseTo(4 * 0.3);
    expect(density[0]![2]).toBeCloseTo(4 * 0.2);
    expect(density[1]![0]).toBeCloseTo(10 * 0.1);
    expect(density[1]![1]).toBeCloseTo(10 * 0.6);
    expect(density[1]![2]).toBeCloseTo(10 * 0.3);
  });

  it("returns empty density for L=0 boundary", () => {
    const density = densityFromFlatBelief({
      L: 0,
      K: 4,
      lot_counts: [],
      age_marginals: [],
    });
    expect(density).toEqual([]);
  });
});

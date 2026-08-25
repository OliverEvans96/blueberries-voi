/**
 * T-115 RED: inventory vs target and age composition from belief vs truth lots.
 * T-C2-A RED: E[f] effective inventory and freshness bands (not τ / Weibull).
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { FlatBelief } from "../engine/types";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";
import type { Day } from "../types";
import * as inv from "./inventoryTarget";
import { inventorySeries, renderInventoryTarget } from "./inventoryTarget";
import { MIN_CHART_DAY_SPAN } from "./axisTicks";

type BeliefDay = { day: number; flatBelief: FlatBelief };

type InventoryOpts = {
  from: "lots" | "belief";
  belief_history?: BeliefDay[];
};

type FreshnessRow = { day: number; fresh: number; mid: number; stale: number };

const LOT_DAY: Day = {
  day: 0,
  lots: [
    { lot_id: 1, n: 10, mean_f: 0.929 },
    { lot_id: 2, n: 5, mean_f: 0.714 },
    { lot_id: 3, n: 3, mean_f: 0.5 },
  ],
  sales_total: 0,
  waste_total: 0,
  demand: 0,
  order_qty: 0,
  arrivals: 0,
  stockout: 0,
  f_at_receipt: null,
};

/** Expected on-hand from belief is Σ lot_counts (6.92), not truth lot n (18). */
const FLAT: FlatBelief = {
  L: 2,
  K: 3,
  lot_counts: [3.6, 3.32],
  f_marginals: [1, 0, 0, 0, 0, 1],
  f_grid: [0.929, 0.714, 0.5],
};

const BELIEF_HISTORY: BeliefDay[] = [{ day: 0, flatBelief: FLAT }];

describe("inventorySeries lots vs belief (T-115)", () => {
  it("truth lots path: on_hand equals sum of lot n", () => {
    const series = inventorySeries([LOT_DAY], DEFAULT_SIM_CONFIG);
    expect(series[0]!.on_hand).toBe(18);
  });

  it("belief path: on_hand equals Σ lot_counts for that day, not the truth lot sum", () => {
    const fn = (
      inv as {
        inventorySeriesFromBelief?: (
          beliefHistory: BeliefDay[],
          config: typeof DEFAULT_SIM_CONFIG,
        ) => Array<{ day: number; on_hand: number; effective: number }>;
        inventorySeries?: (
          history: Day[],
          config: typeof DEFAULT_SIM_CONFIG,
          opts?: InventoryOpts,
        ) => Array<{ day: number; on_hand: number; effective: number }>;
      }
    ).inventorySeriesFromBelief;
    const seriesFn = (
      inv as {
        inventorySeries: (
          history: Day[],
          config: typeof DEFAULT_SIM_CONFIG,
          opts?: InventoryOpts,
        ) => Array<{ day: number; on_hand: number; effective: number }>;
      }
    ).inventorySeries;

    let series: Array<{ day: number; on_hand: number }>;
    if (typeof fn === "function") {
      series = fn(BELIEF_HISTORY, DEFAULT_SIM_CONFIG);
    } else {
      series = seriesFn([LOT_DAY], DEFAULT_SIM_CONFIG, {
        from: "belief",
        belief_history: BELIEF_HISTORY,
      });
    }
    const expected = FLAT.lot_counts.reduce((s, n) => s + n, 0);
    expect(series).toHaveLength(1);
    expect(series[0]!.on_hand).toBeCloseTo(expected);
    expect(series[0]!.on_hand).not.toBe(18);
  });
});

describe("age composition lots vs belief (T-115)", () => {
  it("truth lots path: freshness thirds from lot mean_f and n", () => {
    const fn = (
      inv as {
        fCompositionSeries?: (
          history: Day[],
          opts?: InventoryOpts,
        ) => FreshnessRow[];
      }
    ).fCompositionSeries;
    expect(typeof fn, "expected fCompositionSeries export").toBe("function");
    const rows = fn!([LOT_DAY]);
    expect(rows[0]).toEqual({ day: 0, fresh: 15, mid: 3, stale: 0 });
  });

  it("belief path: bands from expected ages, not truth lots", () => {
    const fn = (
      inv as {
        fCompositionSeries?: (
          history: Day[],
          opts?: InventoryOpts,
        ) => FreshnessRow[];
        fCompositionSeriesFromBelief?: (beliefHistory: BeliefDay[]) => FreshnessRow[];
      }
    ).fCompositionSeriesFromBelief;
    const seriesFn = (
      inv as {
        fCompositionSeries?: (
          history: Day[],
          opts?: InventoryOpts,
        ) => FreshnessRow[];
      }
    ).fCompositionSeries;

    let rows: FreshnessRow[];
    if (typeof fn === "function") {
      rows = fn(BELIEF_HISTORY);
    } else {
      expect(typeof seriesFn).toBe("function");
      rows = seriesFn!([LOT_DAY], {
        from: "belief",
        belief_history: BELIEF_HISTORY,
      });
    }
    // lot 0: all mass at high f; lot 1: all mass at low f
    expect(rows[0]!.fresh).toBeCloseTo(3.6);
    expect(rows[0]!.stale).toBeCloseTo(0);
    expect(rows[0]!.mid).toBeCloseTo(3.32);
    expect(rows[0]!.fresh + rows[0]!.mid + rows[0]!.stale).not.toBe(18);
  });
});

/** f-native wire (T-C2-A): FlatBelief with f_grid / f_marginals. */
type FNativeFlatBelief = {
  L: number;
  K: number;
  lot_counts: number[];
  f_grid: number[];
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

/** E[f]-weighted on-hand: Σ_l n_l Σ_k p(l,k) f_k (ADR 0130 policy helper). */
function expectedEffectiveFromF(flat: FNativeFlatBelief): number {
  let sum = 0;
  for (let l = 0; l < flat.L; l++) {
    const n = flat.lot_counts[l] ?? 0;
    for (let k = 0; k < flat.K; k++) {
      sum +=
        n *
        (flat.f_marginals[l * flat.K + k] ?? 0) *
        (flat.f_grid[k] ?? 0);
    }
  }
  return sum;
}

/** Freshness thirds on [0, 1]: low < 1/3, mid < 2/3, else high. */
function expectedFreshnessBands(flat: FNativeFlatBelief): {
  fresh: number;
  mid: number;
  stale: number;
} {
  const bands = { fresh: 0, mid: 0, stale: 0 };
  for (let l = 0; l < flat.L; l++) {
    const n = flat.lot_counts[l] ?? 0;
    for (let k = 0; k < flat.K; k++) {
      const mass = n * (flat.f_marginals[l * flat.K + k] ?? 0);
      const f = flat.f_grid[k] ?? 0;
      if (f >= 2 / 3) bands.fresh += mass;
      else if (f >= 1 / 3) bands.mid += mass;
      else bands.stale += mass;
    }
  }
  return bands;
}

const F_FLAT = fNativeFlat({
  L: 2,
  K: 3,
  lot_counts: [10, 5],
  f_grid: [0.2, 0.5, 0.9],
  f_marginals: [1, 0, 0, 0, 0, 1],
});

const F_BELIEF_HISTORY: BeliefDay[] = [
  { day: 0, flatBelief: asFWireBelief(F_FLAT) },
];

describe("inventorySeries E[f] effective (T-C2-A / AC-frontend)", () => {
  it("belief path: effective equals Σ lot_counts × E[f|lot], not Weibull(τ)", () => {
    const fn = (
      inv as {
        effectiveInventoryFromFlatBelief?: (
          flat: FlatBelief,
        ) => number;
        inventorySeriesFromBelief?: (
          beliefHistory: BeliefDay[],
          config: typeof DEFAULT_SIM_CONFIG,
        ) => Array<{ day: number; on_hand: number; effective: number }>;
      }
    ).effectiveInventoryFromFlatBelief;

    const expected = expectedEffectiveFromF(F_FLAT);
    expect(expected).toBeCloseTo(10 * 0.2 + 5 * 0.9);

    let effective: number;
    if (typeof fn === "function") {
      effective = fn(asFWireBelief(F_FLAT));
    } else {
      const seriesFn = (
        inv as {
          inventorySeriesFromBelief: (
            beliefHistory: BeliefDay[],
            config: typeof DEFAULT_SIM_CONFIG,
          ) => Array<{ day: number; effective: number }>;
        }
      ).inventorySeriesFromBelief;
      effective = seriesFn(F_BELIEF_HISTORY, DEFAULT_SIM_CONFIG)[0]!.effective;
    }
    expect(effective).toBeCloseTo(expected);

        // E[f] must exceed naive on-hand when mass sits below f=1.
    expect(effective).toBeLessThan(F_FLAT.lot_counts.reduce((s, n) => s + n, 0));
  });

  it("E[f] boundary: all mass at f=0 yields effective 0", () => {
    const flat = fNativeFlat({
      L: 1,
      K: 2,
      lot_counts: [12],
      f_grid: [0, 0.5],
      f_marginals: [1, 0],
    });
    const fn = (
      inv as {
        effectiveInventoryFromFlatBelief?: (flat: FlatBelief) => number;
      }
    ).effectiveInventoryFromFlatBelief;
    const expected = 0;
    if (typeof fn === "function") {
      expect(fn(asFWireBelief(flat))).toBeCloseTo(expected);
    } else {
      const series = (
        inv as {
          inventorySeriesFromBelief: (
            h: BeliefDay[],
            c: typeof DEFAULT_SIM_CONFIG,
          ) => Array<{ effective: number }>;
        }
      ).inventorySeriesFromBelief(
        [{ day: 0, flatBelief: asFWireBelief(flat) }],
        DEFAULT_SIM_CONFIG,
      );
      expect(series[0]!.effective).toBeCloseTo(expected);
    }
  });

  it("E[f] boundary: all mass at f=1 yields effective Σ lot_counts", () => {
    const flat = fNativeFlat({
      L: 2,
      K: 2,
      lot_counts: [4, 6],
      f_grid: [0.5, 1],
      f_marginals: [0, 1, 0, 1],
    });
    const expected = 10;
    const fn = (
      inv as {
        effectiveInventoryFromFlatBelief?: (flat: FlatBelief) => number;
      }
    ).effectiveInventoryFromFlatBelief;
    if (typeof fn === "function") {
      expect(fn(asFWireBelief(flat))).toBeCloseTo(expected);
    } else {
      const series = (
        inv as {
          inventorySeriesFromBelief: (
            h: BeliefDay[],
            c: typeof DEFAULT_SIM_CONFIG,
          ) => Array<{ effective: number }>;
        }
      ).inventorySeriesFromBelief(
        [{ day: 0, flatBelief: asFWireBelief(flat) }],
        DEFAULT_SIM_CONFIG,
      );
      expect(series[0]!.effective).toBeCloseTo(expected);
    }
  });
});

describe("freshness composition bands from f_marginals (T-C2-A / AC-frontend)", () => {
  it("belief path: bands partition by f_grid thirds, not τ-day 0–2 / 3–5 / 6+ buckets", () => {
    const fn = (
      inv as {
        fCompositionSeriesFromBelief?: (
          beliefHistory: BeliefDay[],
        ) => FreshnessRow[];
      }
    ).fCompositionSeriesFromBelief;

    const expected = expectedFreshnessBands(F_FLAT);
    expect(expected.stale).toBeCloseTo(10);
    expect(expected.fresh).toBeCloseTo(5);
    expect(expected.mid).toBeCloseTo(0);

    const row = (
      inv as {
        fCompositionSeriesFromBelief: (
          beliefHistory: BeliefDay[],
        ) => FreshnessRow[];
      }
    ).fCompositionSeriesFromBelief(F_BELIEF_HISTORY)[0]!;
    expect(row.stale).toBeCloseTo(expected.stale);
    expect(row.fresh).toBeCloseTo(expected.fresh);
    expect(row.mid).toBeCloseTo(expected.mid);
    // τ buckets would put f=0.2 and f=0.9 both in "young" if τ were misread from f_grid.
    expect(row.stale).not.toBeCloseTo(0);
    expect(row.fresh).not.toBeCloseTo(15);
  });

  it("f=1/3 lands in mid band (boundary above stale, below fresh)", () => {
    const flat = fNativeFlat({
      L: 1,
      K: 1,
      lot_counts: [7],
      f_grid: [1 / 3],
      f_marginals: [1],
    });
    const history = [{ day: 0, flatBelief: asFWireBelief(flat) }];
    const mid = (
      inv as {
        fCompositionSeriesFromBelief: (
          h: BeliefDay[],
        ) => FreshnessRow[];
      }
    ).fCompositionSeriesFromBelief(history)[0]!.mid;
    expect(mid).toBeCloseTo(7);
  });
});

describe("renderFreshnessComposition freshness legend (T-148)", () => {
  it("draws optional effective inventory overlay as dashed line", () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 320,
      configurable: true,
    });
    inv.renderFreshnessComposition(
      container,
      [LOT_DAY],
      100,
      undefined,
      [{ day: LOT_DAY.day, effective: 8 }],
    );
    expect(container.querySelector(".inv-effective")).not.toBeNull();
    const labels = Array.from(container.querySelectorAll(".legend-label")).map(
      (el) => el.textContent?.trim(),
    );
    expect(labels).toContain("Effective");
  });

  it("uses fresh / fair / old band labels", () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 320,
      configurable: true,
    });
    inv.renderFreshnessComposition(container, [LOT_DAY], 100);
    const labels = Array.from(
      container.querySelectorAll(".legend-label"),
    ).map((el) => el.textContent?.trim());
    expect(labels).toEqual(["fresh", "fair", "old"]);
  });

  it("exports FRESHNESS_LEGEND_BAND and reserves top margin for legend", () => {
    expect(inv.FRESHNESS_LEGEND_BAND).toBe(14);
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 320,
      configurable: true,
    });
    inv.renderFreshnessComposition(container, [LOT_DAY], 100);
    const legend = container.querySelector(".legend");
    expect(legend?.getAttribute("transform")).toBe("translate(44, 4)");
  });

  it("keeps a readable y-axis when all band counts are zero (T-157)", () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 320,
      configurable: true,
    });
    inv.renderFreshnessComposition(container, [LOT_DAY], 100, [
      { day: 0, fresh: 0, mid: 0, stale: 0 },
      { day: 1, fresh: 0, mid: 0, stale: 0 },
    ]);
    const ticks = [...container.querySelectorAll(".axis-y .tick text")].map(
      (t) => t.textContent?.trim() ?? "",
    );
    expect(ticks.length).toBeGreaterThan(0);
    expect(ticks.some((t) => t.includes("0000") || t === "-")).toBe(false);
    expect(ticks.some((t) => Number(t) >= 1)).toBe(true);
  });

  it("applies freshness-young / freshness-mid / freshness-old classes to stacked bar series", () => {
    const container = document.createElement("div");
    Object.defineProperty(container, "clientWidth", {
      value: 320,
      configurable: true,
    });
    inv.renderFreshnessComposition(container, [LOT_DAY], 100);
    const seriesClasses = Array.from(
      container.querySelectorAll(".freshness-series"),
    ).map((el) => el.getAttribute("class")?.trim());
    expect(seriesClasses).toEqual([
      "freshness-series freshness-young",
      "freshness-series freshness-mid",
      "freshness-series freshness-old",
    ]);
  });

  it("uses fresh / fair / old band labels for both truth and belief data rows (T-151 regression: labels must not revert to fraction-threshold wording when the truth overlay supplies rows)", () => {
    function labelsFor(rowsOverride: FreshnessRow[]): (string | undefined)[] {
      const container = document.createElement("div");
      Object.defineProperty(container, "clientWidth", {
        value: 320,
        configurable: true,
      });
      inv.renderFreshnessComposition(container, [LOT_DAY], 100, rowsOverride);
      return Array.from(container.querySelectorAll(".legend-label")).map(
        (el) => el.textContent?.trim(),
      );
    }

    const truthRows = inv.fCompositionSeries([LOT_DAY]);
    const beliefRows = (
      inv as {
        fCompositionSeriesFromBelief: (h: BeliefDay[]) => FreshnessRow[];
      }
    ).fCompositionSeriesFromBelief(BELIEF_HISTORY);

    expect(labelsFor(truthRows)).toEqual(["fresh", "fair", "old"]);
    expect(labelsFor(beliefRows)).toEqual(["fresh", "fair", "old"]);
  });
});

describe("inventory target hover (T-151)", () => {
  function host(width = 320): HTMLElement {
    const el = document.createElement("div");
    Object.defineProperty(el, "clientWidth", { value: width, configurable: true });
    document.body.appendChild(el);
    return el;
  }

  afterEach(() => {
    document.body.replaceChildren();
  });

  it("setInventoryTargetHover toggles hover rule opacity and x position", () => {
    const el = host();
    inv.renderInventoryTarget(el, [LOT_DAY], DEFAULT_SIM_CONFIG, 120);
    inv.setInventoryTargetHover(el, 0);
    const rule = el.querySelector(".hover-rule");
    expect(rule?.getAttribute("opacity")).toBe("1");
    const x1 = Number(rule?.getAttribute("x1"));
    inv.setInventoryTargetHover(el, null);
    expect(rule?.getAttribute("opacity")).toBe("0");
    expect(x1).toBeGreaterThan(0);
  });

  it("setFreshnessCompositionHover toggles hover rule opacity and x position", () => {
    const el = host();
    inv.renderFreshnessComposition(el, [LOT_DAY], 120);
    inv.setFreshnessCompositionHover(el, 0);
    const rule = el.querySelector(".hover-rule");
    expect(rule?.getAttribute("opacity")).toBe("1");
    const x1 = Number(rule?.getAttribute("x1"));
    inv.setFreshnessCompositionHover(el, null);
    expect(rule?.getAttribute("opacity")).toBe("0");
    expect(x1).toBeGreaterThan(0);
  });
});

describe("renderInventoryTarget min day span (T-151)", () => {
  function host(): HTMLElement {
    const el = document.createElement("div");
    Object.defineProperty(el, "clientWidth", { configurable: true, value: 400 });
    document.body.appendChild(el);
    return el;
  }

  afterEach(() => {
    document.body.replaceChildren();
  });

  it("pads x-axis to at least MIN_CHART_DAY_SPAN days with one day of history", () => {
    const el = host();
    renderInventoryTarget(el, [LOT_DAY], DEFAULT_SIM_CONFIG, 120);
    const ticks = [...el.querySelectorAll(".axis-x .tick text")].map((t) =>
      Number(t.textContent),
    );
    expect(Math.max(...ticks) - Math.min(...ticks) + 1).toBeGreaterThanOrEqual(
      MIN_CHART_DAY_SPAN,
    );
  });

  it("renders empty inventory frame when history is empty", () => {
    const el = host();
    renderInventoryTarget(el, [], DEFAULT_SIM_CONFIG, 120);
    expect(el.querySelector("svg.chart-svg")).not.toBeNull();
    expect(el.querySelectorAll(".axis-x .tick").length).toBeGreaterThanOrEqual(
      MIN_CHART_DAY_SPAN,
    );
  });
});

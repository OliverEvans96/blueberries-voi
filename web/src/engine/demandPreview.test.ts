/**
 * T-124 RED (qa-demand): staged demand preview without engine Reset.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "../mock/generate";
import type { DemandSummary } from "./types";
import { ViewModelProjector } from "./projector";
import { bindDemandSliderPreview } from "./demandPreview";

function sampleSummary(): DemandSummary {
  return {
    scale_mu: 30,
    dow_means: [29, 30, 28, 27, 28, 34, 35],
  };
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("demandSummaryFromConfig (T-124 AC-demand)", () => {
  it("returns updated DOW summary from partial demand_mu / demand_vm without Reset", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: DEFAULT_SIM_CONFIG.window_days,
      config: { ...DEFAULT_SIM_CONFIG },
    });
    projector.applySnapshot({
      seq: 0,
      episode_day: 0,
      belief: {
        L: 2,
        K: 4,
        lot_counts: [1, 1],
        f_marginals: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
        f_grid: [0.125, 0.375, 0.625, 0.875],
      },
      demand_summary: sampleSummary(),
    });
    projector.markConfigApplied();

    const fn = (
      projector as ViewModelProjector & {
        demandSummaryFromConfig?: (partial: {
          demand_mu: number;
          demand_vm: number;
        }) => DemandSummary;
      }
    ).demandSummaryFromConfig;
    expect(typeof fn).toBe("function");

    const base = fn!({
      demand_mu: DEFAULT_SIM_CONFIG.demand_mu,
      demand_vm: DEFAULT_SIM_CONFIG.demand_vm,
    });
    expect(base.dow_means).toHaveLength(7);

    const bumped = fn!({
      demand_mu: DEFAULT_SIM_CONFIG.demand_mu + 12,
      demand_vm: DEFAULT_SIM_CONFIG.demand_vm,
    });
    expect(bumped.scale_mu).toBeGreaterThan(base.scale_mu);
    expect(
      bumped.dow_means.some((v, i) => Math.abs(v - base.dow_means[i]!) > 1e-6),
    ).toBe(true);
    expect(projector.getViewModel().config_dirty).toBe(false);
  });
});

describe("demand_mu staged preview chart (T-124 AC-demand)", () => {
  it("re-renders daily demand chart within one animation frame on slider input", async () => {
    const chartHost = document.createElement("div");
    chartHost.id = "chart-demand";
    Object.defineProperty(chartHost, "clientWidth", {
      configurable: true,
      value: 420,
    });
    document.body.appendChild(chartHost);

    const slider = document.createElement("input");
    slider.id = "demand_mu";
    slider.type = "range";
    slider.min = "5";
    slider.max = "80";
    slider.value = String(DEFAULT_SIM_CONFIG.demand_mu);
    document.body.appendChild(slider);

    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      window_days: DEFAULT_SIM_CONFIG.window_days,
      config: { ...DEFAULT_SIM_CONFIG },
    });
    projector.applySnapshot({
      seq: 0,
      episode_day: 0,
      belief: {
        L: 2,
        K: 4,
        lot_counts: [1, 1],
        f_marginals: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
        f_grid: [0.125, 0.375, 0.625, 0.875],
      },
      demand_summary: sampleSummary(),
      history: [
        {
          day: 0,
          lots: [],
          sales_total: 10,
          waste_total: 0,
          demand: 12,
          order_qty: 0,
          arrivals: 0,
          stockout: 2,
          f_at_receipt: null,
        },
      ],
    });

    bindDemandSliderPreview({ chartHost, slider, projector });

    slider.value = String(DEFAULT_SIM_CONFIG.demand_mu + 15);
    slider.dispatchEvent(new Event("input", { bubbles: true }));

    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => resolve());
    });

    expect(chartHost.querySelector(".daily-demand-line")).not.toBeNull();
    expect(chartHost.querySelector("svg.chart-svg")).not.toBeNull();
  });
});

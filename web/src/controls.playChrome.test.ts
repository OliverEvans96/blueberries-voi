/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { mountPlayChrome, type ControlsState } from "./controls";

const initial: ControlsState = {
  orderQty: 24,
  economics: { p_sell: 4, c_unit: 2, c_waste: 1, c_stockout: 3 },
  config: {
    beta: 2,
    eta_ref: 14,
    q10: 2,
    t_ref_c: 4,
    t_store_c: 4,
    sigma: 0.3,
    demand_mu: 30,
    demand_vm: 2,
    case_size: 12,
    lead_time: 2,
    base_stock: 48,
    starting_inv: 48,
    seed: 42,
    obs_scenario: "P0",
    window_days: 14,
    arrival_product: "abdella_all",
    spread_scale: 0.5,
    transit_temp_bias_c: 0,
    f2a_transit_sd: 0.5,
    sensor_sigma: 0,
  },
  configDirty: false,
  episodeDay: 1,
  pendingOrder: 0,
  schedule: null,
};

describe("mountPlayChrome show-truth init", () => {
  it("does not call onShowTruthChange during mount", () => {
    const root = document.createElement("div");
    const onShowTruthChange = vi.fn();
    const api = mountPlayChrome(
      root,
      initial,
      {
        onOrderChange: () => {},
        onAdvance: () => {},
        onReset: () => {},
        onShowTruthChange,
      },
      { showTruth: true, truthClassTarget: document.body },
    );

    expect(onShowTruthChange).not.toHaveBeenCalled();
    expect(document.body.classList.contains("studio--show-truth")).toBe(true);
    api.update(initial);
  });

  it("calls onShowTruthChange when the user toggles truth", () => {
    const root = document.createElement("div");
    const onShowTruthChange = vi.fn();
    mountPlayChrome(
      root,
      initial,
      {
        onOrderChange: () => {},
        onAdvance: () => {},
        onReset: () => {},
        onShowTruthChange,
      },
      { showTruth: false, truthClassTarget: document.body },
    );

    const btn = root.querySelector("#btn-show-truth") as HTMLButtonElement;
    btn.click();
    expect(onShowTruthChange).toHaveBeenCalledOnce();
    expect(onShowTruthChange).toHaveBeenCalledWith(true);
  });
});

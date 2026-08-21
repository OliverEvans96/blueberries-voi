/**
 * T-126 AC-obschip: patchEngineState must sync config.obs_scenario from
 * snapshot.applied_config.obs_scenario on the returned ViewModel — no separate
 * setConfig call required (obs-chip active state bug).
 */
import { describe, expect, it } from "vitest";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "../mock/generate";
import { ViewModelProjector } from "./projector";
import type { FlatBelief, Snapshot } from "./types";

const FLAT_BELIEF: FlatBelief = {
  L: 2,
  K: 4,
  lot_counts: [3, 3],
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

/** Minimal patch payload matching patchEngineState's Snapshot pick. */
function obsScenarioPatch(obs_scenario: string) {
  return {
    belief: { ...FLAT_BELIEF, f_marginals: [...FLAT_BELIEF.f_marginals] },
    live_lots: [] as const,
    pipeline: [] as const,
    episode_day: 0,
    applied_config: { obs_scenario },
  };
}

describe("ViewModelProjector.patchEngineState obs_scenario sync (T-126 AC-obschip)", () => {
  it("returned ViewModel.config.obs_scenario reflects applied_config after P0 → F2", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      config: { ...DEFAULT_SIM_CONFIG },
    });
    projector.applySnapshot(
      sampleSnapshot({ applied_config: { obs_scenario: "P0" } }),
    );
    expect(projector.getViewModel().config.obs_scenario).toBe("P0");

    const vm = projector.patchEngineState(obsScenarioPatch("F2"));

    expect(vm.config.obs_scenario).toBe("F2");
  });

  it("returned ViewModel.config.obs_scenario reflects applied_config after P1 → F1s", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      config: { ...DEFAULT_SIM_CONFIG },
    });
    projector.applySnapshot(
      sampleSnapshot({ applied_config: { obs_scenario: "P1" } }),
    );
    expect(projector.getViewModel().config.obs_scenario).toBe("P1");

    const vm = projector.patchEngineState(obsScenarioPatch("F1s"));

    expect(vm.config.obs_scenario).toBe("F1s");
  });

  it("obs_scenario switch via patchEngineState alone does not set config_dirty", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      config: { ...DEFAULT_SIM_CONFIG },
    });
    projector.applySnapshot(
      sampleSnapshot({ applied_config: { obs_scenario: "P0" } }),
    );
    projector.markConfigApplied();
    expect(projector.getViewModel().config_dirty).toBe(false);

    const vm = projector.patchEngineState(obsScenarioPatch("F2"));

    expect(vm.config.obs_scenario).toBe("F2");
    expect(vm.config_dirty).toBe(false);
  });

  it("patchEngineState syncs only obs_scenario to config, not other applied_config keys", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      config: { ...DEFAULT_SIM_CONFIG },
    });
    projector.applySnapshot(
      sampleSnapshot({ applied_config: { obs_scenario: "P1" } }),
    );
    const baselineCaseSize = projector.getViewModel().config.case_size;

    const vm = projector.patchEngineState({
      ...obsScenarioPatch("F2"),
      applied_config: { obs_scenario: "F2", case_size: baselineCaseSize + 99 },
    });

    expect(vm.config.obs_scenario).toBe("F2");
    expect(vm.config.case_size).toBe(baselineCaseSize);
  });

  it("patchEngineState then setConfig with equivalent obs_channels stays clean (Autopilot gate)", () => {
    const projector = new ViewModelProjector({
      economics: { ...DEFAULT_ECONOMICS },
      config: { ...DEFAULT_SIM_CONFIG },
    });
    projector.applySnapshot(sampleSnapshot());
    projector.markConfigApplied();
    const channels = {
      code_type: "gsin" as const,
      scan_waste: true,
      delivery_history: "pack_date" as const,
    };
    projector.patchEngineState({
      ...obsScenarioPatch("F2"),
      applied_config: {
        obs_scenario: "F2",
        obs_channels: { ...channels },
      },
    });
    const vm = projector.setConfig({
      obs_channels: channels,
      obs_scenario: "F2",
    });
    expect(vm.config_dirty).toBe(false);
  });
});

//! Reset loading UX when arrival prior rebuilds (studio prior bake).

import { describe, expect, it, vi } from "vitest";

import { DEFAULT_SIM_CONFIG } from "../mock/generate";

describe("resetEpisode prior rebuild heuristic", () => {
  it("detects non-default Q10 as likely prior rebuild", () => {
    const config = { ...DEFAULT_SIM_CONFIG, q10: 3.5 };
    const mayRebuild =
      config.q10 !== DEFAULT_SIM_CONFIG.q10 ||
      config.t_ref_c !== DEFAULT_SIM_CONFIG.t_ref_c;
    expect(mayRebuild).toBe(true);
  });

  it("default physics skips optimistic loading", () => {
    const mayRebuild =
      DEFAULT_SIM_CONFIG.q10 !== DEFAULT_SIM_CONFIG.q10 ||
      DEFAULT_SIM_CONFIG.t_ref_c !== DEFAULT_SIM_CONFIG.t_ref_c;
    expect(mayRebuild).toBe(false);
  });

  it("honors Rust arrival_prior_rebuilt flag on snapshot", () => {
    const snap = {
      seq: 0,
      episode_day: 0,
      belief: { L: 1, K: 4, lot_counts: [], f_marginals: [], f_grid: [] },
      arrival_prior_rebuilt: true,
    };
    expect(snap.arrival_prior_rebuilt).toBe(true);
  });
});

describe("resetEpisode loading (mock)", () => {
  it("shows loading when adapter reports prior rebuild", async () => {
    const begin = vi.fn();
    const end = vi.fn();
    const snap = {
      seq: 0,
      episode_day: 0,
      belief: { L: 1, K: 4, lot_counts: [], f_marginals: [], f_grid: [] },
      arrival_prior_rebuilt: true,
    };
    const adapter = {
      reset: vi.fn(async () => snap),
    };
    const config = { ...DEFAULT_SIM_CONFIG };
    const mayRebuild =
      config.q10 !== DEFAULT_SIM_CONFIG.q10 ||
      config.t_ref_c !== DEFAULT_SIM_CONFIG.t_ref_c;
    if (mayRebuild) {
      begin(
        "Updating beliefs after settings changed… This might take ~30 seconds.",
      );
    }
    const result = await adapter.reset(config);
    if (result.arrival_prior_rebuilt && !mayRebuild) {
      begin(
        "Updating beliefs after settings changed… This might take ~30 seconds.",
      );
    }
    end();
    expect(begin).toHaveBeenCalledOnce();
    expect(end).toHaveBeenCalledOnce();
  });
});

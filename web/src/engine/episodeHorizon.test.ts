/**
 * T-112 RED: 90-day full-episode horizon — no 14-day rolling drop.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MockAdapter } from "../mock/adapter";
import {
  DEFAULT_SIM_CONFIG,
  stepSimulation,
  createInitialState,
} from "../mock/generate";
import type { EngineAdapter } from "./adapter";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_SRC = join(HERE, "..");
const CONTROLS_TS = join(WEB_SRC, "controlsPlayMount.tsx");
const PLAY_CHROME_TS = join(WEB_SRC, "react/PlayChrome.tsx");
const MAIN_TS = join(WEB_SRC, "react/studioLogic.ts");
const AUTOPILOT_TS = join(WEB_SRC, "autopilotLoop.ts");
const PNL_TOTALS_TS = join(WEB_SRC, "charts/pnlTotals.ts");
const GENERATE_TS = join(WEB_SRC, "mock/generate.ts");
const ADAPTER_TS = join(WEB_SRC, "mock/adapter.ts");
const PROJECTOR_TS = join(HERE, "projector.ts");

describe("T-112 mock adapter never drops history until Reset", () => {
  it("drop_oldest is always false and history grows past 14 steps", async () => {
    const adapter = new MockAdapter(42) as unknown as EngineAdapter;
    await adapter.init({});
    const days: number[] = [];
    for (let i = 0; i < 20; i++) {
      const delta = await adapter.step(8);
      expect(delta.drop_oldest).toBe(false);
      days.push(delta.day.day);
    }
    const snap = await adapter.reset({});
    expect(snap.episode_day).toBe(0);
    expect(snap.history ?? []).toHaveLength(0);

    const again = new MockAdapter(7) as unknown as EngineAdapter;
    const init = await again.init({});
    const startLen = init.history?.length ?? 0;
    for (let i = 0; i < 16; i++) {
      await again.step(0);
    }
    // No public snapshot-after-step; infer via a projector-free length check
    // by stepping and ensuring drop_oldest never flipped (above) plus generate.
    expect(startLen).toBeLessThanOrEqual(90);
  });

  it("stepSimulation appends and does not slice(-window_days)", () => {
    const cfg = { ...DEFAULT_SIM_CONFIG, window_days: 14, seed: 1 };
    let state = createInitialState(cfg);
    const start = state.history.length;
    for (let i = 0; i < 20; i++) {
      const out = stepSimulation(state, 0, cfg);
      state = out.state;
    }
    expect(state.history.length).toBe(start + 20);
    expect(state.history.length).toBeGreaterThan(14);
  });

  it("DEFAULT_SIM_CONFIG.window_days is episode length 90, not a 14-day chart window", () => {
    expect(DEFAULT_SIM_CONFIG.window_days).toBe(90);
  });
});

describe("T-112 generate/adapter source: no rolling slice", () => {
  it("mock generate does not slice history to window_days", () => {
    const src = readFileSync(GENERATE_TS, "utf8");
    expect(src).not.toMatch(/slice\(\s*-?\s*config\.window_days\s*\)/);
    expect(src).not.toMatch(/slice\(\s*-window/);
  });

  it("mock adapter drop_oldest is always false", () => {
    const src = readFileSync(ADAPTER_TS, "utf8");
    expect(src).toMatch(/drop_oldest:\s*false/);
    expect(src).not.toMatch(
      /drop_oldest\s*=\s*this\.state\.history\.length\s*>=\s*this\.config\.window_days/,
    );
  });

  it("projector does not slice to windowDays or drop on drop_oldest", () => {
    const src = readFileSync(PROJECTOR_TS, "utf8");
    expect(src).not.toMatch(/slice\(\s*-this\.windowDays\s*\)/);
    expect(src).not.toMatch(/if\s*\(\s*delta\.drop_oldest/);
  });
});

describe("T-112 studio UI episode complete + PnL episode totals", () => {
  it("PnL labels are episode totals, not Window …", () => {
    expect(existsSync(PNL_TOTALS_TS)).toBe(true);
    const src = readFileSync(PNL_TOTALS_TS, "utf8");
    expect(src).not.toMatch(/Window revenue/);
    expect(src).not.toMatch(/Window cost/);
    expect(src).not.toMatch(/Window profit/);
    expect(src).toMatch(/Episode (revenue|profit)|episode total/i);
  });

  it("controls has no user-facing window_days rolling chart knob", () => {
    const src = readFileSync(CONTROLS_TS, "utf8") + readFileSync(PLAY_CHROME_TS, "utf8");
    expect(src).not.toMatch(/id:\s*"window_days"/);
    expect(src).not.toMatch(/window_days.*group/);
    expect(src).not.toMatch(/label:\s*"window/i);
  });

  it("at day 90 Advance is disabled and copy tells the user to Reset", () => {
    const controls = readFileSync(CONTROLS_TS, "utf8") + readFileSync(PLAY_CHROME_TS, "utf8");
    const main = readFileSync(MAIN_TS, "utf8");
    const combined = `${controls}\n${main}`;
    expect(combined).toMatch(/90/);
    expect(combined).toMatch(/episode.*(finish|finished|complete|end)/i);
    expect(combined).toMatch(/Reset/);
    expect(combined).toMatch(
      /episodeDay\s*>=\s*90|episode_day\s*>=\s*90|EPISODE_(LEN|HORIZON|DAYS)/,
    );
    expect(controls).toMatch(/btnAdvance\.disabled|id="btn-advance"[\s\S]*disabled=/);
  });

  it("Autopilot pauses or refuses play at episode day 90", () => {
    expect(existsSync(AUTOPILOT_TS)).toBe(true);
    const main = readFileSync(MAIN_TS, "utf8");
    const loop = readFileSync(AUTOPILOT_TS, "utf8");
    const combined = `${main}\n${loop}`;
    expect(combined).toMatch(/90/);
    expect(combined).toMatch(/pause\(|refuse|isRunning\(\)|episode/i);
  });
});

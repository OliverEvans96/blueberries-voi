/**
 * T-101 scripted smoke: Autopilot play ≥3 MockAdapter.act ticks under damped_sw.
 *
 * Exit 0 when three DayDeltas land with advancing episode_day and no overlapping
 * act calls. Exit non-zero if the Autopilot path is broken.
 *
 * Smoke *evidence* (`.team/qa/T-101-smoke.md`) is implement's job — this file is
 * only the runnable harness.
 *
 * Run from web/: `npm run smoke:autopilot`
 * (or `npx vitest run scripts/smoke-autopilot-mock.ts`)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAutopilotLoop } from "../src/autopilotLoop";
import type { ActOpts, DayDelta } from "../src/engine/types";
import { MockAdapter } from "../src/mock/adapter";

const REQUIRED_TICKS = 3;

describe("T-101 Autopilot MockAdapter smoke harness", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it(`plays ≥${REQUIRED_TICKS} damped_sw act ticks without overlapping calls`, async () => {
    const adapter = new MockAdapter(42);
    const ticks: DayDelta[] = [];
    let inFlight = 0;
    let overlapSeen = false;
    let actCalls = 0;

    const loop = createAutopilotLoop({
      act: async (opts?: ActOpts) => {
        if (inFlight > 0) {
          overlapSeen = true;
        }
        inFlight += 1;
        actCalls += 1;
        try {
          return await adapter.act(opts);
        } finally {
          inFlight -= 1;
        }
      },
      applyDelta: (_delta: DayDelta) => {
        /* projector / UI apply — not required for harness */
      },
      getOpts: (): ActOpts => ({
        policy: "damped_sw",
        alpha: 0.9,
        rho: 0.8,
      }),
      getIntervalMs: () => 50,
      isConfigDirty: () => false,
      onError: (err: unknown) => {
        throw err instanceof Error ? err : new Error(String(err));
      },
      onTick: (delta: DayDelta) => {
        ticks.push(delta);
        if (ticks.length >= REQUIRED_TICKS) {
          loop.pause();
        }
      },
    });

    loop.play();

    // Drive wall-clock schedule until pause after REQUIRED_TICKS.
    for (let i = 0; i < REQUIRED_TICKS + 2; i++) {
      await vi.runOnlyPendingTimersAsync();
      await Promise.resolve();
      await Promise.resolve();
      if (ticks.length >= REQUIRED_TICKS && !loop.isRunning()) {
        break;
      }
    }

    expect(
      overlapSeen,
      "Autopilot must not overlap MockAdapter.act calls",
    ).toBe(false);
    expect(actCalls).toBeGreaterThanOrEqual(REQUIRED_TICKS);
    expect(ticks.length).toBeGreaterThanOrEqual(REQUIRED_TICKS);

    // MockAdapter warms a window_days history, so episode_day starts > 1;
    // Autopilot smoke only requires advancing DayDeltas + order_qty for UI sync.
    for (let i = 0; i < REQUIRED_TICKS; i++) {
      const delta = ticks[i]!;
      expect(delta.day, `tick ${i} must carry a day record`).toBeTruthy();
      expect(
        typeof delta.day.order_qty,
        `tick ${i} day.order_qty (UI sync signal)`,
      ).toBe("number");
      expect(delta.seq).toBe(i + 1);
      if (i > 0) {
        expect(delta.episode_day).toBeGreaterThan(ticks[i - 1]!.episode_day);
        expect(delta.seq).toBeGreaterThan(ticks[i - 1]!.seq);
      }
    }

    expect(loop.isRunning()).toBe(false);
  });
});

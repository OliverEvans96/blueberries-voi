/**
 * T-100 RED: Autopilot single-flight loop, interval defaults, pause/error/dirty,
 * order sync, Play chrome Autopilot Play/Pause contracts.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DayDelta } from "./engine/types";

const HERE = dirname(fileURLToPath(import.meta.url));
const AUTOPILOT_LOOP_TS = join(HERE, "autopilotLoop.ts");
const CONTROLS_TS = join(HERE, "controlsPlayMount.tsx");
const PLAY_CHROME_TS = join(HERE, "react/PlayChrome.tsx");
const MAIN_TS = join(HERE, "react/studioLogic.ts");

function sampleDelta(orderQty: number, episodeDay = 1): DayDelta {
  return {
    seq: episodeDay,
    episode_day: episodeDay,
    day: {
      day: episodeDay - 1,
      demand: 10,
      order_qty: orderQty,
      sales_total: 0,
      waste_total: 0,
      arrivals: 0,
      L: 0,
    },
    drop_oldest: false,
    belief: null,
    live_lots: [],
    pipeline: [],
  };
}

type AutopilotDeps = {
  act: (opts?: unknown) => Promise<DayDelta>;
  applyDelta: (delta: DayDelta) => void;
  getOpts: () => unknown;
  getIntervalMs: () => number;
  isConfigDirty: () => boolean;
  onError: (err: unknown) => void;
  onTick?: (delta: DayDelta) => void;
};

type AutopilotHandle = {
  play: () => void;
  pause: () => void;
  isRunning: () => boolean;
};

type AutopilotModule = {
  createAutopilotLoop?: (deps: AutopilotDeps) => AutopilotHandle;
  defaultIntervalMsForPolicy?: (policy: string) => number;
};

async function loadAutopilotModule(): Promise<AutopilotModule> {
  expect(
    existsSync(AUTOPILOT_LOOP_TS),
    "expected web/src/autopilotLoop.ts",
  ).toBe(true);
  return (await import("./autopilotLoop")) as AutopilotModule;
}

async function flushMicrotasks(times = 5): Promise<void> {
  for (let i = 0; i < times; i++) {
    await Promise.resolve();
  }
}

describe("defaultIntervalMsForPolicy (T-100)", () => {
  it("returns 500 for damped_sw and constant, 1000 for rollout", async () => {
    const mod = await loadAutopilotModule();
    expect(
      typeof mod.defaultIntervalMsForPolicy,
      "expected export defaultIntervalMsForPolicy",
    ).toBe("function");
    const fn = mod.defaultIntervalMsForPolicy!;
    expect(fn("damped_sw")).toBe(500);
    expect(fn("constant")).toBe(500);
    expect(fn("rollout")).toBe(1000);
  });
});

describe("createAutopilotLoop single-flight + scheduling (T-100)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("exports createAutopilotLoop with play / pause / isRunning", async () => {
    const mod = await loadAutopilotModule();
    expect(typeof mod.createAutopilotLoop).toBe("function");
    const handle = mod.createAutopilotLoop!({
      act: async () => sampleDelta(8),
      applyDelta: () => {},
      getOpts: () => ({ policy: "damped_sw" }),
      getIntervalMs: () => 500,
      isConfigDirty: () => false,
      onError: () => {},
    });
    expect(typeof handle.play).toBe("function");
    expect(typeof handle.pause).toBe("function");
    expect(typeof handle.isRunning).toBe("function");
  });

  it("never starts a second act while one is in flight (single-flight)", async () => {
    const mod = await loadAutopilotModule();
    expect(typeof mod.createAutopilotLoop).toBe("function");

    let resolveAct!: (d: DayDelta) => void;
    const act = vi.fn(
      () =>
        new Promise<DayDelta>((resolve) => {
          resolveAct = resolve;
        }),
    );
    const applyDelta = vi.fn();
    const handle = mod.createAutopilotLoop!({
      act,
      applyDelta,
      getOpts: () => ({ policy: "damped_sw" }),
      getIntervalMs: () => 100,
      isConfigDirty: () => false,
      onError: () => {},
    });

    handle.play();
    await flushMicrotasks();
    expect(act).toHaveBeenCalledTimes(1);
    expect(handle.isRunning()).toBe(true);

    // Wall-clock advances while act is still pending — must not overlap.
    await vi.advanceTimersByTimeAsync(10_000);
    await flushMicrotasks();
    expect(act).toHaveBeenCalledTimes(1);

    resolveAct(sampleDelta(16));
    await flushMicrotasks();
    expect(applyDelta).toHaveBeenCalledTimes(1);

    // After apply, next tick may schedule; still only one completed flight.
    await vi.advanceTimersByTimeAsync(100);
    await flushMicrotasks();
    expect(act).toHaveBeenCalledTimes(2);
  });

  it("schedules next tick with max(0, intervalMs - elapsed) via fake timers", async () => {
    const mod = await loadAutopilotModule();
    expect(typeof mod.createAutopilotLoop).toBe("function");

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    const intervalMs = 500;
    const actElapsedMs = 200;

    const act = vi.fn(async () => {
      // Simulate RPC work that consumes wall-clock time.
      await new Promise<void>((resolve) => {
        setTimeout(resolve, actElapsedMs);
      });
      return sampleDelta(24);
    });
    const applyDelta = vi.fn();

    const handle = mod.createAutopilotLoop!({
      act,
      applyDelta,
      getOpts: () => ({ policy: "damped_sw" }),
      getIntervalMs: () => intervalMs,
      isConfigDirty: () => false,
      onError: () => {},
    });

    handle.play();
    await flushMicrotasks();

    // Drive the in-act delay to completion.
    await vi.advanceTimersByTimeAsync(actElapsedMs);
    await flushMicrotasks();
    expect(applyDelta).toHaveBeenCalledTimes(1);

    const expectedDelay = Math.max(0, intervalMs - actElapsedMs);
    const scheduleDelays = setTimeoutSpy.mock.calls
      .map((c) => c[1])
      .filter((d): d is number => typeof d === "number");
    expect(
      scheduleDelays,
      `expected a post-act schedule delay of ${expectedDelay}ms`,
    ).toContain(expectedDelay);

    // Elapsed > interval → delay clamps to 0.
    handle.pause();
    setTimeoutSpy.mockClear();
    const slowAct = vi.fn(async () => {
      await new Promise<void>((resolve) => {
        setTimeout(resolve, 800);
      });
      return sampleDelta(8, 2);
    });
    const handleSlow = mod.createAutopilotLoop!({
      act: slowAct,
      applyDelta,
      getOpts: () => ({ policy: "damped_sw" }),
      getIntervalMs: () => 500,
      isConfigDirty: () => false,
      onError: () => {},
    });
    handleSlow.play();
    await flushMicrotasks();
    await vi.advanceTimersByTimeAsync(800);
    await flushMicrotasks();
    const slowDelays = setTimeoutSpy.mock.calls
      .map((c) => c[1])
      .filter((d): d is number => typeof d === "number");
    expect(slowDelays).toContain(0);
    handleSlow.pause();
  });

  it("uses getIntervalMs (user override) for scheduling, not a hardcoded policy default", async () => {
    const mod = await loadAutopilotModule();
    expect(typeof mod.createAutopilotLoop).toBe("function");

    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    const userInterval = 750;
    const act = vi.fn(async () => sampleDelta(8));
    // Instant act → elapsed ≈ 0 → delay ≈ userInterval.
    const handle = mod.createAutopilotLoop!({
      act,
      applyDelta: () => {},
      getOpts: () => ({ policy: "rollout" }),
      getIntervalMs: () => userInterval,
      isConfigDirty: () => false,
      onError: () => {},
    });

    handle.play();
    await flushMicrotasks();
    expect(act).toHaveBeenCalledTimes(1);

    const delays = setTimeoutSpy.mock.calls
      .map((c) => c[1])
      .filter((d): d is number => typeof d === "number");
    expect(
      delays,
      "user getIntervalMs(750) must win over rollout default 1000",
    ).toContain(userInterval);
    handle.pause();
  });

  it("pause clears the scheduled timer and stops further acts", async () => {
    const mod = await loadAutopilotModule();
    expect(typeof mod.createAutopilotLoop).toBe("function");

    const act = vi.fn(async () => sampleDelta(8));
    const handle = mod.createAutopilotLoop!({
      act,
      applyDelta: () => {},
      getOpts: () => ({ policy: "damped_sw" }),
      getIntervalMs: () => 200,
      isConfigDirty: () => false,
      onError: () => {},
    });

    handle.play();
    await flushMicrotasks();
    expect(act).toHaveBeenCalledTimes(1);
    handle.pause();
    expect(handle.isRunning()).toBe(false);

    await vi.advanceTimersByTimeAsync(5_000);
    await flushMicrotasks();
    expect(act).toHaveBeenCalledTimes(1);
  });
});

describe("createAutopilotLoop pause on error / config_dirty + order sync (T-100)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("pauses and surfaces onError when act rejects", async () => {
    const mod = await loadAutopilotModule();
    expect(typeof mod.createAutopilotLoop).toBe("function");

    const err = new Error("act failed");
    const act = vi.fn(async () => {
      throw err;
    });
    const onError = vi.fn();
    const applyDelta = vi.fn();
    const handle = mod.createAutopilotLoop!({
      act,
      applyDelta,
      getOpts: () => ({ policy: "damped_sw" }),
      getIntervalMs: () => 100,
      isConfigDirty: () => false,
      onError,
    });

    handle.play();
    await flushMicrotasks();
    expect(onError).toHaveBeenCalledWith(err);
    expect(applyDelta).not.toHaveBeenCalled();
    expect(handle.isRunning()).toBe(false);

    await vi.advanceTimersByTimeAsync(5_000);
    await flushMicrotasks();
    expect(act).toHaveBeenCalledTimes(1);
  });

  it("pauses when isConfigDirty becomes true (no further acts)", async () => {
    const mod = await loadAutopilotModule();
    expect(typeof mod.createAutopilotLoop).toBe("function");

    let dirty = false;
    const act = vi.fn(async () => sampleDelta(8));
    const handle = mod.createAutopilotLoop!({
      act,
      applyDelta: () => {
        dirty = true;
      },
      getOpts: () => ({ policy: "damped_sw" }),
      getIntervalMs: () => 100,
      isConfigDirty: () => dirty,
      onError: () => {},
    });

    handle.play();
    await flushMicrotasks();
    expect(act).toHaveBeenCalledTimes(1);
    // After successful tick, dirty is true — loop must pause before next act.
    await vi.advanceTimersByTimeAsync(5_000);
    await flushMicrotasks();
    expect(act).toHaveBeenCalledTimes(1);
    expect(handle.isRunning()).toBe(false);
  });

  it("invokes onTick with the applied delta so order_qty can sync", async () => {
    const mod = await loadAutopilotModule();
    expect(typeof mod.createAutopilotLoop).toBe("function");

    const delta = sampleDelta(32);
    const onTick = vi.fn();
    const applyDelta = vi.fn();
    const handle = mod.createAutopilotLoop!({
      act: async () => delta,
      applyDelta,
      getOpts: () => ({ policy: "constant", order_qty: 0 }),
      getIntervalMs: () => 500,
      isConfigDirty: () => false,
      onError: () => {},
      onTick,
    });

    handle.play();
    await flushMicrotasks();
    expect(applyDelta).toHaveBeenCalledWith(delta);
    expect(onTick).toHaveBeenCalledWith(delta);
    const passed = onTick.mock.calls[0]?.[0] as DayDelta;
    expect(
      (passed.day as { order_qty?: number }).order_qty,
    ).toBe(32);
    handle.pause();
  });
});

describe("Play chrome Autopilot Play/Pause (T-100)", () => {
  it("mountPlayChrome exposes Autopilot Play and Autopilot Pause labels", () => {
    const src = readFileSync(CONTROLS_TS, "utf8") + readFileSync(PLAY_CHROME_TS, "utf8");
    expect(src).toMatch(/function\s+mountPlayChrome\b/);
    expect(
      src,
      "expected Autopilot Play accessible name/label in play chrome",
    ).toMatch(/Autopilot\s+Play/);
    expect(
      src,
      "expected Autopilot Pause accessible name/label in play chrome",
    ).toMatch(/Autopilot\s+Pause/);
    // T-100 open question: Advance disabled while Autopilot runs (not step+pause).
    // T-112 also disables Advance at episode day 90.
    expect(src).toMatch(/Advance is disabled/);
    expect(src).toMatch(
      /btnAdvance\.disabled\s*=\s*(running|autopilotRunning\s*\|\|)|disabled=\{autopilotRunning \|\| atEnd\}/,
    );
  });

  it("react/studioLogic.ts wires createAutopilotLoop (adapter.act path, not generate autopilot)", () => {
    const src = readFileSync(MAIN_TS, "utf8");
    expect(src).toMatch(/createAutopilotLoop/);
    expect(src).toMatch(/autopilotLoop/);
    // Product Autopilot must not route through generate.ts runDay(..., autopilot).
    expect(src).not.toMatch(
      /runDay\s*\([^)]*autopilot|\.act\s*=\s*undefined/,
    );
  });
});

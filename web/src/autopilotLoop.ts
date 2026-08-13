/**
 * Single-flight Autopilot wall-clock loop (T-100 / ADR 0112).
 *
 * await act → applyDelta → schedule next with max(0, intervalMs - elapsed).
 * Never overlaps act calls. Does not use generate.ts runDay(..., autopilot).
 */

import type { ActOpts, DayDelta } from "./engine/types";

export type AutopilotDeps = {
  act: (opts?: ActOpts) => Promise<DayDelta>;
  applyDelta: (delta: DayDelta) => void;
  getOpts: () => ActOpts;
  getIntervalMs: () => number;
  isConfigDirty: () => boolean;
  onError: (err: unknown) => void;
  onTick?: (delta: DayDelta) => void;
};

export type AutopilotHandle = {
  play: () => void;
  pause: () => void;
  isRunning: () => boolean;
};

/** Default cadence: 500ms for damped_sw/constant, 1000ms for rollout. */
export function defaultIntervalMsForPolicy(policy: string): number {
  return policy === "rollout" ? 1000 : 500;
}

export function createAutopilotLoop(deps: AutopilotDeps): AutopilotHandle {
  let running = false;
  let inFlight = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  function clearTimer(): void {
    if (timer != null) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function pause(): void {
    running = false;
    clearTimer();
  }

  function scheduleNext(elapsedMs: number): void {
    if (!running) return;
    if (deps.isConfigDirty()) {
      pause();
      return;
    }
    const delay = Math.max(0, deps.getIntervalMs() - elapsedMs);
    timer = setTimeout(() => {
      timer = null;
      void tick();
    }, delay);
  }

  async function tick(): Promise<void> {
    if (!running || inFlight) return;
    if (deps.isConfigDirty()) {
      pause();
      return;
    }
    inFlight = true;
    const t0 = performance.now();
    try {
      const delta = await deps.act(deps.getOpts());
      const elapsed = performance.now() - t0;
      // Always apply a completed in-flight act (last applied day), then stop if paused.
      deps.applyDelta(delta);
      deps.onTick?.(delta);
      inFlight = false;
      if (!running || deps.isConfigDirty()) {
        pause();
        return;
      }
      scheduleNext(elapsed);
    } catch (err) {
      inFlight = false;
      pause();
      deps.onError(err);
    }
  }

  function play(): void {
    if (running) return;
    running = true;
    void tick();
  }

  return {
    play,
    pause,
    isRunning: () => running,
  };
}

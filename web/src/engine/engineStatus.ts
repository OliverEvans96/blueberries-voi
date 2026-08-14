/**
 * Studio engine ready-chip: loading until adapter.init() settles.
 *
 * Ready means a finished init (Pyodide + wheel + EngineSession bind, or HTTP
 * session create) — not merely `new Worker()`. Failure is a red Failed chip;
 * `#studio-error` still carries the long message.
 */

import type { StudioAdapterKind } from "./studioAdapter";

export type EngineStatusKind = "loading" | "ready" | "error";

export type EngineStatusChip = {
  kind: EngineStatusKind;
  status: EngineStatusKind;
  label: string;
  dot: "yellow" | "green" | "red";
};

export type EngineStatusListener = (kind: EngineStatusKind) => void;

/** Minimal element surface for vitest (node) and the browser DOM. */
export type EngineStatusTarget = {
  dataset: { status?: string };
  querySelector: (sel: string) => { textContent: string | null } | null;
};

export function engineStatusChip(
  kind: EngineStatusKind,
  adapterKind?: StudioAdapterKind,
): EngineStatusChip {
  if (kind === "ready") {
    return { kind, status: "ready", label: "Ready", dot: "green" };
  }
  if (kind === "error") {
    return { kind, status: "error", label: "Failed", dot: "red" };
  }
  const label =
    adapterKind === "http" || adapterKind === "mock" ? "Connecting" : "Loading";
  return { kind, status: "loading", label, dot: "yellow" };
}

export function applyEngineStatusChip(
  el: EngineStatusTarget,
  kind: EngineStatusKind,
  adapterKind?: StudioAdapterKind,
): void {
  const chip = engineStatusChip(kind, adapterKind);
  el.dataset.status = chip.status;
  const label = el.querySelector(".engine-status-label");
  if (label) label.textContent = chip.label;
}

export type EngineStatusTracker = {
  get(): EngineStatusKind;
  set(kind: EngineStatusKind): void;
  subscribe(fn: EngineStatusListener): () => void;
  follow<T>(promise: Promise<T>): Promise<T>;
};

/**
 * Tracks loading → ready|error from an init promise. Constructing a Worker
 * must not call `set("ready")`.
 */
export function createEngineStatusTracker(
  initial: EngineStatusKind = "loading",
): EngineStatusTracker {
  let current: EngineStatusKind = initial;
  const listeners = new Set<EngineStatusListener>();

  function set(kind: EngineStatusKind): void {
    if (kind === current) return;
    current = kind;
    for (const fn of listeners) fn(current);
  }

  return {
    get() {
      return current;
    },
    set,
    subscribe(fn: EngineStatusListener): () => void {
      listeners.add(fn);
      fn(current);
      return () => {
        listeners.delete(fn);
      };
    },
    async follow<T>(promise: Promise<T>): Promise<T> {
      set("loading");
      try {
        const result = await promise;
        set("ready");
        return result;
      } catch (err) {
        set("error");
        throw err;
      }
    },
  };
}

/**
 * T-057 / T-125: studio EngineAdapter selection (WASM default, ADR 0129).
 *
 * Env flags (documented in `.team/qa/T-057-smoke.md` and `web/.env.example`):
 * - `VITE_ENGINE_ADAPTER` — explicit override: `wasm` | `mock`
 * - `VITE_WASM_WORKER_URL` / `VITE_WASM_PKG_URL` / `VITE_WASM_ASSET_BASE_URL` — optional CDN overrides
 */

import type { EngineAdapter } from "./adapter";
import { MockAdapter } from "../mock/adapter";
import { WasmAdapter } from "./wasmAdapter";

/** Selected studio engine backend. */
export type StudioAdapterKind = "wasm" | "mock";

/**
 * Vite / process-like env surface used for adapter selection.
 * Implementer may document exact names; tests pin these keys as the contract.
 */
export type StudioEnv = {
  MODE?: string;
  DEV?: boolean;
  PROD?: boolean;
  /** Explicit override: "wasm" | "mock". */
  VITE_ENGINE_ADAPTER?: string;
  VITE_WASM_WORKER_URL?: string;
  VITE_WASM_PKG_URL?: string;
  VITE_WASM_ASSET_BASE_URL?: string;
};

/** Sentinel for resolveLocalStudioDefaults — worker is bundled by Vite (T-144). */
export const BUNDLED_WASM_WORKER = "bundled";

export type CreateStudioAdapterOpts = {
  env?: StudioEnv;
  /** Force kind (skips env resolution). */
  kind?: StudioAdapterKind;
  workerUrl?: string;
  pkgUrl?: string;
  fetch?: typeof fetch;
};

export type LocalStudioDefaults = {
  workerUrl: string;
  /** WASM pkg base URL (legacy field name retained for callers). */
  wheelUrl: string;
};

/** Local readiness — bundled worker + pkg via Vite graph (T-144). */
export function resolveLocalStudioDefaults(): LocalStudioDefaults {
  return {
    workerUrl: BUNDLED_WASM_WORKER,
    wheelUrl: "",
  };
}

/**
 * Footer copy for the resolved adapter kind.
 * Live WASM must not claim fake or mock data (T-074 / T-125).
 */
export function studioFooterCopy(kind: StudioAdapterKind): string {
  if (kind === "wasm") {
    return "Live WASM studio · blueberries-voi · D3 + Vite";
  }
  return "Mock debug studio · blueberries-voi · D3 + Vite";
}

/** Minimal element-like surface for vitest (node) and the browser DOM. */
export type StudioErrorTarget = {
  textContent: string | null;
  hidden: boolean;
};

function studioErrorConsolePrefix(message: string): string {
  if (/^Init failed/i.test(message)) return "Studio init failed";
  if (/^Advance failed/i.test(message)) return "Studio advance failed";
  if (/^Reset failed/i.test(message)) return "Studio reset failed";
  if (/^Autopilot failed/i.test(message)) return "Studio autopilot failed";
  return "Studio adapter error";
}

/**
 * Surface an adapter init/step failure to the user (non-silent) and log it.
 * When `target` is omitted, looks up `#studio-error` in the document if present.
 * `cause` (when an Error) is passed to console.error so tracebacks stay inspectable.
 */
export function reportStudioAdapterError(
  message: string,
  target?: StudioErrorTarget | null,
  cause?: unknown,
  root?: ParentNode | null,
): void {
  const prefix = studioErrorConsolePrefix(message);
  if (cause instanceof Error) {
    console.error(prefix, cause);
  } else if (cause !== undefined) {
    console.error(prefix, cause);
  } else {
    console.error(prefix, message);
  }

  const el =
    target ??
    (root?.querySelector("#studio-error") as StudioErrorTarget | null) ??
    (typeof document !== "undefined"
      ? (document.querySelector("#studio-error") as StudioErrorTarget | null)
      : null);
  if (!el) return;
  el.textContent = message;
  el.hidden = false;
}

/**
 * Resolve which adapter the studio should use.
 *
 * Contract (T-125): default wasm; mock only when explicitly selected.
 */
export function resolveStudioAdapterKind(env: StudioEnv = {}): StudioAdapterKind {
  const override = env.VITE_ENGINE_ADAPTER?.trim().toLowerCase();
  if (override === "wasm" || override === "mock") {
    return override;
  }
  return "wasm";
}

/**
 * Construct the studio EngineAdapter for the resolved (or forced) kind.
 */
export function createStudioAdapter(
  opts: CreateStudioAdapterOpts = {},
): EngineAdapter {
  const env = opts.env ?? {};
  const kind = opts.kind ?? resolveStudioAdapterKind(env);

  if (kind === "wasm") {
    const wasmOpts: { workerUrl?: string; assetBaseUrl?: string; pkgUrl?: string } =
      {};
    const envWorker = env.VITE_WASM_WORKER_URL?.trim();
    const fromOpts = opts.workerUrl;
    const optsLooksPyodide =
      typeof fromOpts === "string" && /pyodide/i.test(fromOpts);
    if (envWorker) {
      wasmOpts.workerUrl = envWorker;
    } else if (fromOpts && !optsLooksPyodide) {
      wasmOpts.workerUrl = fromOpts;
    }
    const assetBase =
      env.VITE_WASM_ASSET_BASE_URL?.trim()
      ?? env.VITE_WASM_PKG_URL?.trim()
      ?? opts.pkgUrl?.trim();
    if (assetBase) {
      wasmOpts.assetBaseUrl = assetBase;
    }
    return new WasmAdapter(wasmOpts);
  }

  return new MockAdapter();
}

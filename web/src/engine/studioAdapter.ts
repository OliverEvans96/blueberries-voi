/**
 * T-057 / T-074: studio EngineAdapter selection (dev=HttpAdapter, prod=PyodideAdapter).
 *
 * Env flags (also documented in `.team/qa/T-057-smoke.md` and `web/.env.example`):
 * - `VITE_ENGINE_ADAPTER` — explicit override: `http` | `pyodide` | `wasm` | `mock`
 * - `VITE_ENGINE_API_BASE_URL` / `VITE_API_BASE_URL` — ASGI base for HttpAdapter
 * - `VITE_PYODIDE_WORKER_URL` / `VITE_PYODIDE_WHEEL_URL` — PyodideAdapter URLs
 *
 * Local readiness defaults (ADR 0108 / T-074): localhost API, Vite-served worker + wheel.
 */

import type { EngineAdapter } from "./adapter";
import { HttpAdapter } from "./httpAdapter";
import { MockAdapter } from "../mock/adapter";
import { PyodideAdapter } from "./pyodideAdapter";
import { WasmAdapter } from "./wasmAdapter";

/** Selected studio engine backend. */
export type StudioAdapterKind = "http" | "pyodide" | "wasm" | "mock";

/**
 * Vite / process-like env surface used for adapter selection.
 * Implementer may document exact names; tests pin these keys as the contract.
 */
export type StudioEnv = {
  MODE?: string;
  DEV?: boolean;
  PROD?: boolean;
  /** Explicit override: "http" | "pyodide" | "wasm" | "mock". */
  VITE_ENGINE_ADAPTER?: string;
  VITE_ENGINE_API_BASE_URL?: string;
  VITE_API_BASE_URL?: string;
  VITE_PYODIDE_WORKER_URL?: string;
  VITE_PYODIDE_WHEEL_URL?: string;
  VITE_WASM_WORKER_URL?: string;
  VITE_WASM_PKG_URL?: string;
};

export type CreateStudioAdapterOpts = {
  env?: StudioEnv;
  /** Force kind (skips env resolution). */
  kind?: StudioAdapterKind;
  baseUrl?: string;
  workerUrl?: string;
  wheelUrl?: string;
  fetch?: typeof fetch;
};

/** Documented local dual-mode defaults (T-072 / T-074). */
export const LOCAL_DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_PYODIDE_WORKER_URL = "/packaging/pyodide/worker.js";
const DEFAULT_PYODIDE_WHEEL_URL =
  "/wheels/blueberries_voi-0.1.0-py3-none-any.whl";
const DEFAULT_WASM_WORKER_URL = "/packaging/wasm/worker.js";
const DEFAULT_WASM_PKG_URL = "/wasm/";

export type LocalStudioDefaults = {
  apiBaseUrl: string;
  workerUrl: string;
  wheelUrl: string;
};

/** Local readiness URLs — not GitHub Release placeholders. */
export function resolveLocalStudioDefaults(): LocalStudioDefaults {
  return {
    apiBaseUrl: LOCAL_DEFAULT_API_BASE_URL,
    workerUrl: DEFAULT_PYODIDE_WORKER_URL,
    wheelUrl: DEFAULT_PYODIDE_WHEEL_URL,
  };
}

/**
 * Footer copy for the resolved adapter kind.
 * Live Http / Pyodide must not claim fake or mock data (T-074).
 */
export function studioFooterCopy(kind: StudioAdapterKind): string {
  if (kind === "http") {
    return "Live HTTP studio · blueberries-voi · D3 + Vite";
  }
  if (kind === "pyodide") {
    return "Live Pyodide studio · blueberries-voi · D3 + Vite";
  }
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
 * `cause` (when an Error) is passed to console.error so Python tracebacks stay inspectable.
 */
export function reportStudioAdapterError(
  message: string,
  target?: StudioErrorTarget | null,
  cause?: unknown,
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
    (typeof document !== "undefined"
      ? (document.querySelector("#studio-error") as StudioErrorTarget | null)
      : null);
  if (!el) return;
  el.textContent = message;
  el.hidden = false;
}

function apiBaseUrl(env: StudioEnv): string | undefined {
  const raw = env.VITE_ENGINE_API_BASE_URL ?? env.VITE_API_BASE_URL;
  if (typeof raw === "string" && raw.trim().length > 0) {
    return raw.trim();
  }
  return undefined;
}

function isProd(env: StudioEnv): boolean {
  return env.PROD === true || env.MODE === "production";
}

/**
 * Resolve which adapter the studio should use.
 *
 * Contract (T-057):
 * - explicit `VITE_ENGINE_ADAPTER` wins
 * - else production / PROD → pyodide
 * - else development with API base URL configured → http
 * - mock only when explicitly selected (debug)
 */
export function resolveStudioAdapterKind(env: StudioEnv = {}): StudioAdapterKind {
  const override = env.VITE_ENGINE_ADAPTER?.trim().toLowerCase();
  if (
    override === "http" ||
    override === "pyodide" ||
    override === "wasm" ||
    override === "mock"
  ) {
    return override;
  }
  if (isProd(env)) {
    return "pyodide";
  }
  if (apiBaseUrl(env) !== undefined) {
    return "http";
  }
  // Never silent-mock: unconfigured non-prod still prefers the demo backend.
  return "pyodide";
}

/**
 * Construct the studio EngineAdapter for the resolved (or forced) kind.
 */
export function createStudioAdapter(
  opts: CreateStudioAdapterOpts = {},
): EngineAdapter {
  const env = opts.env ?? {};
  const kind = opts.kind ?? resolveStudioAdapterKind(env);

  if (kind === "http") {
    return new HttpAdapter({
      baseUrl: opts.baseUrl ?? apiBaseUrl(env) ?? LOCAL_DEFAULT_API_BASE_URL,
      fetch: opts.fetch,
    });
  }

  if (kind === "pyodide") {
    const workerUrl =
      opts.workerUrl
      ?? env.VITE_PYODIDE_WORKER_URL
      ?? DEFAULT_PYODIDE_WORKER_URL;
    const wheelUrl =
      opts.wheelUrl
      ?? env.VITE_PYODIDE_WHEEL_URL
      ?? DEFAULT_PYODIDE_WHEEL_URL;
    return new PyodideAdapter({ workerUrl, wheelUrl });
  }

  if (kind === "wasm") {
    const fromOpts = opts.workerUrl;
    const optsLooksPyodide =
      typeof fromOpts === "string" && /pyodide/i.test(fromOpts);
    const workerUrl =
      env.VITE_WASM_WORKER_URL
      ?? (fromOpts && !optsLooksPyodide ? fromOpts : undefined)
      ?? DEFAULT_WASM_WORKER_URL;
    const pkgUrl = env.VITE_WASM_PKG_URL ?? DEFAULT_WASM_PKG_URL;
    return new WasmAdapter({ workerUrl, pkgUrl });
  }

  return new MockAdapter();
}

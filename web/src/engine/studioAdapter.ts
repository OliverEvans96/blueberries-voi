/**
 * T-057: studio EngineAdapter selection (dev=HttpAdapter, prod=PyodideAdapter).
 *
 * Env flags (also documented in `.team/qa/T-057-smoke.md`):
 * - `VITE_ENGINE_ADAPTER` — explicit override: `http` | `pyodide` | `mock`
 * - `VITE_ENGINE_API_BASE_URL` / `VITE_API_BASE_URL` — ASGI base for HttpAdapter
 * - `VITE_PYODIDE_WORKER_URL` / `VITE_PYODIDE_WHEEL_URL` — PyodideAdapter URLs
 */

import type { EngineAdapter } from "./adapter";
import { HttpAdapter } from "./httpAdapter";
import { MockAdapter } from "../mock/adapter";
import { PyodideAdapter } from "./pyodideAdapter";

/** Selected studio engine backend. */
export type StudioAdapterKind = "http" | "pyodide" | "mock";

/**
 * Vite / process-like env surface used for adapter selection.
 * Implementer may document exact names; tests pin these keys as the contract.
 */
export type StudioEnv = {
  MODE?: string;
  DEV?: boolean;
  PROD?: boolean;
  /** Explicit override: "http" | "pyodide" | "mock". */
  VITE_ENGINE_ADAPTER?: string;
  VITE_ENGINE_API_BASE_URL?: string;
  VITE_API_BASE_URL?: string;
  VITE_PYODIDE_WORKER_URL?: string;
  VITE_PYODIDE_WHEEL_URL?: string;
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

const DEFAULT_PYODIDE_WORKER_URL = "/packaging/pyodide/worker.js";
const DEFAULT_PYODIDE_WHEEL_URL =
  "https://github.com/oliver/blueberries-voi/releases/download/v0.1.0/" +
  "blueberries_voi-0.1.0-py3-none-any.whl";

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
  if (override === "http" || override === "pyodide" || override === "mock") {
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
      baseUrl: opts.baseUrl ?? apiBaseUrl(env),
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

  return new MockAdapter();
}

/**
 * T-057: studio EngineAdapter selection (dev=HttpAdapter, prod=PyodideAdapter).
 *
 * RED stub — returns the wrong kind / always MockAdapter until implement wires
 * defaults. Env flag names are documented by implementer in the mockup README.
 */

import type { EngineAdapter } from "./adapter";
import { MockAdapter } from "../mock/adapter";

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
  // RED: invert the contract so selection assertions fail until implement.
  const override = env.VITE_ENGINE_ADAPTER?.trim().toLowerCase();
  if (override === "mock") return "http";
  if (override === "http") return "mock";
  if (override === "pyodide") return "mock";
  if (env.PROD === true || env.MODE === "production") return "http";
  return "mock";
}

/**
 * Construct the studio EngineAdapter for the resolved (or forced) kind.
 */
export function createStudioAdapter(
  opts: CreateStudioAdapterOpts = {},
): EngineAdapter {
  // RED: always MockAdapter so prod/dev defaults fail until implement.
  void opts;
  return new MockAdapter() as unknown as EngineAdapter;
}

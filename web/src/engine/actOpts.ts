/**
 * Shared ActOpts normalizer (T-098 / ADR 0112).
 *
 * Callers may pass nested `{ policy, budgets }` and/or flat budget knobs.
 * Adapters fold once here: HTTP nests under `budgets`; Pyodide flattens.
 */

import type { ActBudgets, ActOpts } from "./types";

export const ACT_BUDGET_KEYS = [
  "alpha",
  "rho",
  "H",
  "n_rollout_paths",
  "candidate_case_radius",
  "n_particles",
  "order_qty",
  "q",
] as const satisfies ReadonlyArray<keyof ActBudgets>;

export type HttpActBody = {
  policy?: string;
  budgets: ActBudgets;
};

/** Fold nested + flat knobs into HTTP `{ policy?, budgets }` (no flat siblings). */
export function toHttpActBody(opts?: ActOpts): HttpActBody {
  const budgets: ActBudgets = {};
  if (opts?.budgets) {
    for (const key of ACT_BUDGET_KEYS) {
      const v = opts.budgets[key];
      if (v !== undefined) {
        budgets[key] = v;
      }
    }
  }
  if (opts) {
    for (const key of ACT_BUDGET_KEYS) {
      const v = opts[key];
      if (v !== undefined) {
        budgets[key] = v;
      }
    }
  }
  const body: HttpActBody = { budgets };
  if (opts?.policy !== undefined) {
    body.policy = opts.policy;
  }
  return body;
}

/** Flatten to worker / Pyodide `act` params (no nested `budgets` object). */
export function toFlatActParams(opts?: ActOpts): Record<string, unknown> {
  const { policy, budgets } = toHttpActBody(opts);
  const flat: Record<string, unknown> = { ...budgets };
  if (policy !== undefined) {
    flat.policy = policy;
  }
  return flat;
}

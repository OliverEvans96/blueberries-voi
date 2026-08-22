/**
 * T-098: typed ActOpts, shared normalize helpers, MockAdapter.act (T-125 WASM-only).
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MockAdapter } from "../mock/adapter";
import { normalizeActBudgets, toFlatActParams } from "./actOpts";
import {
  FORBIDDEN_ENGINE_KEYS,
  type ActOpts,
} from "./types";

const HERE = dirname(fileURLToPath(import.meta.url));
const TYPES_SRC = join(HERE, "types.ts");
const MOCK_ADAPTER_SRC = join(HERE, "../mock/adapter.ts");
const ACT_OPTS_SRC = join(HERE, "actOpts.ts");

const BUDGET_KEYS = [
  "alpha",
  "rho",
  "H",
  "n_rollout_paths",
  "candidate_case_radius",
  "n_particles",
  "order_qty",
  "q",
] as const;

/** Mixed nested + flat caller shape adapters must accept. */
const CALLER_OPTS: ActOpts = {
  policy: "damped_sw",
  alpha: 0.9,
  budgets: {
    rho: 0.8,
    H: 7,
    n_rollout_paths: 2,
    candidate_case_radius: 1,
    n_particles: 200,
  },
};

function collectKeys(value: unknown, found = new Set<string>()): Set<string> {
  if (value !== null && typeof value === "object") {
    if (Array.isArray(value)) {
      for (const item of value) collectKeys(item, found);
    } else {
      for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
        found.add(k);
        collectKeys(v, found);
      }
    }
  }
  return found;
}

describe("Typed ActOpts (T-098 / ADR 0117)", () => {
  it("exports ActPolicyName, ActBudgets, and typed ActOpts (not only Record)", () => {
    const src = readFileSync(TYPES_SRC, "utf8");
    expect(src).toMatch(/export\s+type\s+ActPolicyName\b/);
    expect(src).toMatch(/export\s+type\s+ActBudgets\b/);
    expect(src).toMatch(/export\s+type\s+ActOpts\b/);
    expect(src).not.toMatch(
      /export\s+type\s+ActOpts\s*=\s*Record\s*<\s*string\s*,\s*unknown\s*>\s*;/,
    );
    for (const key of BUDGET_KEYS) {
      expect(src).toMatch(new RegExp(`\\b${key}\\b`));
    }
    for (const policy of [
      "damped_sw",
      "sw",
      "rollout",
      "ctl",
      "rollout_order",
      "constant",
      "const",
      "fixed",
    ]) {
      expect(src).toContain(`"${policy}"`);
    }
  });

  it("caller-facing ActOpts compiles at use sites (policy + nested/flat budgets)", () => {
    const nested: ActOpts = {
      policy: "rollout",
      budgets: { alpha: 0.9, rho: 0.8, H: 7 },
    };
    const flat: ActOpts = {
      policy: "constant",
      order_qty: 16,
      q: 16,
    };
    expect(nested.policy).toBe("rollout");
    expect(flat.order_qty ?? flat.q).toBe(16);
  });
});

describe("Shared normalize surface (T-098 / T-125)", () => {
  it("normalizeActBudgets folds nested + flat knobs under budgets", () => {
    const body = normalizeActBudgets(CALLER_OPTS);
    expect(body.policy).toBe("damped_sw");
    expect(body.budgets).toEqual(
      expect.objectContaining({
        alpha: 0.9,
        rho: 0.8,
        H: 7,
        n_rollout_paths: 2,
        candidate_case_radius: 1,
        n_particles: 200,
      }),
    );
    for (const key of BUDGET_KEYS) {
      expect(body).not.toHaveProperty(key);
    }
  });

  it("toFlatActParams flattens for wasm worker act RPC (no nested budgets)", () => {
    const flat = toFlatActParams(CALLER_OPTS);
    expect(flat).not.toHaveProperty("budgets");
    expect(flat.policy).toBe("damped_sw");
    expect(flat.alpha).toBe(0.9);
    expect(flat.rho).toBe(0.8);
    expect(flat.H).toBe(7);
    expect(flat.n_rollout_paths).toBe(2);
    expect(flat.candidate_case_radius).toBe(1);
    expect(flat.n_particles).toBe(200);
  });

  it("actOpts module exports shared normalize helpers", () => {
    const src = readFileSync(ACT_OPTS_SRC, "utf8");
    expect(src).toMatch(/export\s+function\s+normalizeActBudgets/);
    expect(src).toMatch(/export\s+function\s+toFlatActParams/);
  });
});

describe("MockAdapter.act returns DayDelta (T-098)", () => {
  it("exists, advances one mock day, and chooses order from opts", async () => {
    const adapter = new MockAdapter(42);
    await adapter.init({});
    const before = await adapter.reset({});
    const seqBefore = before.seq;
    const dayBefore = before.episode_day;

    expect(typeof adapter.act).toBe("function");
    // First act advances day 0→1; second act lands on a default order weekday (Tue).
    await adapter.act!({ policy: "constant", order_qty: 16 });
    const delta = await adapter.act!({
      policy: "constant",
      order_qty: 16,
    });

    expect(delta).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        episode_day: expect.any(Number),
        day: expect.any(Object),
        drop_oldest: expect.any(Boolean),
      }),
    );
    expect(delta.seq).toBe(seqBefore + 2);
    expect(delta.episode_day).toBe(dayBefore + 1);
    const day = delta.day as { order_qty?: number };
    expect(day.order_qty).toBe(16);
  });

  it("act DayDelta omits forbidden presentation keys", async () => {
    const adapter = new MockAdapter(42);
    await adapter.init({});
    expect(typeof adapter.act).toBe("function");
    const delta = await adapter.act!({ policy: "damped_sw", alpha: 0.9 });
    const keys = collectKeys(delta);
    for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
      expect(keys.has(forbidden)).toBe(false);
    }
    expect(delta).not.toHaveProperty("pnl_series");
    expect(delta).not.toHaveProperty("economics");
  });

  it("documents that mock act is not numeric-parity with Python rollout / damped SW", () => {
    const src = readFileSync(MOCK_ADAPTER_SRC, "utf8");
    expect(src).toMatch(/\bact\s*\(/);
    expect(src).toMatch(/not.*numeric|≠|!=.*parity|not.*parity/i);
    expect(src).toMatch(/rollout_order|DampedSurvivalWeightedPolicy|Python/i);
  });
});

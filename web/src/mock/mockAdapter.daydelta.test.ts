/**
 * T-054 RED: EngineAdapter contract + MockAdapter speaking DayDelta (not ViewModel).
 */
import { describe, expect, it } from "vitest";
import type { EngineAdapter } from "../engine/adapter";
import { FORBIDDEN_ENGINE_KEYS } from "../engine/types";
import { MockAdapter } from "./adapter";

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

describe("EngineAdapter interface (MockAdapter)", () => {
  it("exposes init / step / step_n / reset returning Promises", async () => {
    const adapter = new MockAdapter(42) as unknown as EngineAdapter;

    expect(typeof adapter.init).toBe("function");
    expect(typeof adapter.step).toBe("function");
    expect(typeof adapter.step_n).toBe("function");
    expect(typeof adapter.reset).toBe("function");

    const snap = await adapter.init({});
    expect(snap).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        episode_day: expect.any(Number),
        belief: expect.objectContaining({
          L: expect.any(Number),
          K: expect.any(Number),
          lot_counts: expect.any(Array),
          age_marginals: expect.any(Array),
          tau_grid: expect.any(Array),
        }),
      }),
    );

    const delta = await adapter.step(8);
    expect(delta).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        episode_day: expect.any(Number),
        day: expect.any(Object),
        drop_oldest: expect.any(Boolean),
      }),
    );

    const batch = await adapter.step_n([8, 8]);
    expect(Array.isArray(batch)).toBe(true);
    expect(batch).toHaveLength(2);
    expect(batch[0]).toEqual(
      expect.objectContaining({ day: expect.any(Object), drop_oldest: expect.any(Boolean) }),
    );

    const resetSnap = await adapter.reset({});
    expect(resetSnap).toEqual(
      expect.objectContaining({
        seq: expect.any(Number),
        belief: expect.objectContaining({ age_marginals: expect.any(Array) }),
      }),
    );
  });

  it("init Snapshot belief is flat (len age_marginals === L*K)", async () => {
    const adapter = new MockAdapter(42) as unknown as EngineAdapter;
    const snap = await adapter.init({});
    expect(snap.belief).toEqual(
      expect.objectContaining({
        L: expect.any(Number),
        K: expect.any(Number),
        lot_counts: expect.any(Array),
        age_marginals: expect.any(Array),
        tau_grid: expect.any(Array),
      }),
    );
    const { L, K, lot_counts, age_marginals, tau_grid } = snap.belief;
    expect(lot_counts).toHaveLength(L);
    expect(age_marginals).toHaveLength(L * K);
    expect(tau_grid).toHaveLength(K);
    for (const row of age_marginals) {
      expect(Array.isArray(row)).toBe(false);
    }
  });
});

describe("MockAdapter DayDelta protocol (forbidden ViewModel on engine path)", () => {
  it("step does not ship full ViewModel / presentation keys", async () => {
    const adapter = new MockAdapter(42) as unknown as EngineAdapter;
    await adapter.init({});
    const delta = await adapter.step(8);
    const keys = collectKeys(delta);
    for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
      expect(keys.has(forbidden)).toBe(false);
    }
    // Nested density must not appear under belief either.
    expect(delta).not.toHaveProperty("pnl_series");
    expect(delta).not.toHaveProperty("economics");
    if (delta.belief) {
      expect(delta.belief).not.toHaveProperty("density");
    }
  });

  it("init Snapshot rejects presentation keys (no ViewModel from engine)", async () => {
    const adapter = new MockAdapter(42) as unknown as EngineAdapter;
    const snap = await adapter.init({});
    const keys = collectKeys(snap);
    for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
      expect(keys.has(forbidden)).toBe(false);
    }
  });

  it("step_n returns only DayDelta elements (no ViewModel fields)", async () => {
    const adapter = new MockAdapter(42) as unknown as EngineAdapter;
    expect(typeof adapter.step_n).toBe("function");
    await adapter.init({});
    const deltas = await adapter.step_n([0, 8, 16]);
    expect(deltas).toHaveLength(3);
    for (const delta of deltas) {
      const keys = collectKeys(delta);
      for (const forbidden of FORBIDDEN_ENGINE_KEYS) {
        expect(keys.has(forbidden)).toBe(false);
      }
      expect(delta).toEqual(
        expect.objectContaining({
          day: expect.any(Object),
          drop_oldest: expect.any(Boolean),
        }),
      );
    }
  });
});

describe("MockAdapter step return contract", () => {
  it("step result is a DayDelta, not a ViewModel with pnl_series", async () => {
    const adapter = new MockAdapter(42) as unknown as EngineAdapter;
    await adapter.init({});
    const delta = await adapter.step(8);
    expect(delta).toHaveProperty("drop_oldest");
    expect(delta).toHaveProperty("day");
    expect(delta).not.toHaveProperty("pnl_series");
    expect(delta).not.toHaveProperty("pnl_totals");
    expect(delta).not.toHaveProperty("ghost");
  });
});
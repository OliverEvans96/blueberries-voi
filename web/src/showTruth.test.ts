/**
 * T-115 RED: persist show-truth in localStorage; gate lots via truthLots().
 */
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Lot } from "./types";

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOW_TRUTH_TS = join(HERE, "showTruth.ts");
const SHOW_TRUTH_KEY = "blueberries-voi-studio-show-truth";

const MEMORY_STORE = new Map<string, string>();

afterEach(() => {
  MEMORY_STORE.clear();
  vi.unstubAllGlobals();
});

function stubLocalStorage(): void {
  vi.stubGlobal("localStorage", {
    getItem(key: string): string | null {
      return MEMORY_STORE.has(key) ? MEMORY_STORE.get(key)! : null;
    },
    setItem(key: string, value: string): void {
      MEMORY_STORE.set(key, value);
    },
    removeItem(key: string): string | void {
      MEMORY_STORE.delete(key);
    },
    clear(): void {
      MEMORY_STORE.clear();
    },
  });
}

const LOTS: Lot[] = [
  { lot_id: 1, n: 8, mean_f: 0.857 },
  { lot_id: 2, n: 4, mean_f: 0.643 },
];

describe("showTruth persistence (T-115)", () => {
  it("ships showTruth.ts module", () => {
    expect(existsSync(SHOW_TRUTH_TS), "expected web/src/showTruth.ts").toBe(
      true,
    );
  });

  it("loadShowTruth defaults to false when storage is empty", async () => {
    stubLocalStorage();
    const { loadShowTruth } = await import("./showTruth");
    expect(loadShowTruth()).toBe(false);
    expect(MEMORY_STORE.has(SHOW_TRUTH_KEY)).toBe(false);
  });

  it("saveShowTruth then loadShowTruth round-trips; stored values are exactly true/false strings", async () => {
    stubLocalStorage();
    const { loadShowTruth, saveShowTruth } = await import("./showTruth");
    saveShowTruth(true);
    expect(MEMORY_STORE.get(SHOW_TRUTH_KEY)).toBe("true");
    expect(loadShowTruth()).toBe(true);
    saveShowTruth(false);
    expect(MEMORY_STORE.get(SHOW_TRUTH_KEY)).toBe("false");
    expect(loadShowTruth()).toBe(false);
  });

  it("truthLots(false, lots) is empty; truthLots(true, lots) returns the lots", async () => {
    const { truthLots } = await import("./showTruth");
    expect(truthLots(false, LOTS)).toEqual([]);
    expect(truthLots(true, LOTS)).toEqual(LOTS);
  });
});

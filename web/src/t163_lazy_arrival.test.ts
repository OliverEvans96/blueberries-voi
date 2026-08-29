/**
 * T-163 — lazy arrival_summary load (init omits wire; section-open fetch).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const WEB_SRC = fileURLToPath(new URL(".", import.meta.url));

function read(rel: string): string {
  return readFileSync(join(WEB_SRC, rel), "utf8");
}

describe("T-163 lazy arrival chart", () => {
  it("wasmAdapter exposes fetchArrivalSummary RPC", () => {
    const src = read("engine/wasmAdapter.ts");
    expect(src).toMatch(/fetchArrivalSummary/);
    expect(src).toMatch(/arrival_summary/);
  });

  it("studioLogic fetches arrival wire when Arrival section opens", () => {
    const src = read("react/studioLogic.ts");
    expect(src).toMatch(/ensureArrivalSummary/);
    expect(src).toMatch(/id === "arrival"/);
    expect(src).toMatch(/renderArrivalPriorPlaceholder/);
    expect(src).toMatch(/chart-arrival-prior-overlay/);
  });

  it("controls wrap arrival prior chart with loading overlay slot", () => {
    const src = read("controls.ts");
    expect(src).toMatch(/chart-arrival-prior-overlay/);
    expect(src).toMatch(/chart-arrival-prior-slot/);
  });
});

/**
 * T-099 / T-127: Autopilot section (renamed from controller).
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  SECTION_STORAGE_KEY,
  STUDIO_SECTIONS,
  loadSection,
  saveSection,
  type SectionId,
} from "./sections";

const HERE = dirname(fileURLToPath(import.meta.url));
const LAYOUT_TS = join(HERE, "react/StudioLayout.tsx");
const LOGIC_TS = join(HERE, "react/studioLogic.ts");
const CONTROLS_TS = join(HERE, "controls.ts");
const SECTIONS_TS = join(HERE, "sections.ts");
const CONTROLLER_ORDERS_TS = join(HERE, "charts/controllerOrders.ts");

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
    removeItem(key: string): void {
      MEMORY_STORE.delete(key);
    },
    clear(): void {
      MEMORY_STORE.clear();
    },
  });
}

describe("Autopilot section registration (T-127 shell)", () => {
  it("STUDIO_SECTIONS has autopilot as the 8th entry (nav key 8)", () => {
    expect(STUDIO_SECTIONS).toHaveLength(8);
    expect(STUDIO_SECTIONS[7]).toBeDefined();
    expect(STUDIO_SECTIONS[7]!.id).toBe("autopilot");
    expect(STUDIO_SECTIONS[7]!.label).toMatch(/^Autopilot$/i);
  });

  it("SectionId union in sections.ts includes autopilot", () => {
    const src = readFileSync(SECTIONS_TS, "utf8");
    const typeBlock = src.match(
      /export\s+type\s+SectionId\s*=([\s\S]*?);/,
    )?.[1];
    expect(typeBlock, "expected SectionId type alias").toBeDefined();
    expect(typeBlock).toMatch(/\|\s*"autopilot"/);
  });

  it("loadSection / saveSection accept autopilot and round-trip", () => {
    stubLocalStorage();
    saveSection("autopilot" as SectionId);
    expect(MEMORY_STORE.get(SECTION_STORAGE_KEY)).toBe("autopilot");
    expect(loadSection()).toBe("autopilot");
  });

  it("migrates legacy controller storage key to autopilot", () => {
    stubLocalStorage();
    MEMORY_STORE.set(SECTION_STORAGE_KEY, "controller");
    expect(loadSection()).toBe("autopilot");
  });

  it("autopilot plotIds include orders plot and reuse plot-inventory", () => {
    const autopilot = STUDIO_SECTIONS.find((s) => s.id === "autopilot");
    expect(autopilot).toBeDefined();
    const ids = autopilot!.plotIds;
    expect(ids).toContain("plot-controller-orders");
    expect(ids).toContain("plot-inventory");
  });
});

describe("Autopilot controls (T-099 legacy controller block)", () => {
  it("controls.ts mounts a controller block with policy / alpha / rho / budgets / interval", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/data-section=["']controller["']/);

    for (const policy of ["damped_sw", "rollout", "constant"] as const) {
      expect(
        src,
        `expected policy chip data-policy="${policy}"`,
      ).toMatch(new RegExp(`data-policy=["']${policy}["']`));
    }

    for (const id of [
      "alpha",
      "rho",
      "H",
      "n_rollout_paths",
      "candidate_case_radius",
      "n_particles",
    ] as const) {
      expect(
        src,
        `expected control input id for ${id}`,
      ).toMatch(new RegExp(`id=["']${id}["']`));
    }

    expect(
      src,
      "expected Autopilot interval control (ms)",
    ).toMatch(/id=["']interval(Ms)?["']|interval-ms|intervalMs/);
  });
});

describe("Autopilot chart wiring (T-099)", () => {
  it("ships controllerOrders chart module", () => {
    expect(
      existsSync(CONTROLLER_ORDERS_TS),
      "expected web/src/charts/controllerOrders.ts",
    ).toBe(true);
  });

  it("react/studioLogic.ts mounts controller orders in Run today strip (T-127)", () => {
    const layout = readFileSync(LAYOUT_TS, "utf8");
    const logic = readFileSync(LOGIC_TS, "utf8");
    expect(logic).toMatch(/controllerOrders|renderControllerOrders/);
    expect(layout).toMatch(/id="chart-controller-orders"/);
  });
});

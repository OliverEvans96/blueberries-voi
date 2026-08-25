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
const TUNING_DRAWER_TS = join(HERE, "react/TuningDrawer.tsx");
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
  it("STUDIO_SECTIONS has autopilot as the 7th entry (nav key 7)", () => {
    expect(STUDIO_SECTIONS).toHaveLength(7);
    expect(STUDIO_SECTIONS[6]).toBeDefined();
    expect(STUDIO_SECTIONS[6]!.id).toBe("autopilot");
    expect(STUDIO_SECTIONS[6]!.label).toMatch(/^Autopilot$/i);
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

  it("autopilot plotIds include separate orders, spoilage, and age composition", () => {
    const autopilot = STUDIO_SECTIONS.find((s) => s.id === "autopilot");
    expect(autopilot).toBeDefined();
    const ids = autopilot!.plotIds;
    expect(ids).toContain("plot-controller-orders");
    expect(ids).toContain("plot-spoil");
    expect(ids).toContain("plot-age-comp");
    expect(ids).not.toContain("plot-orders-spoilage");
  });
});

describe("Autopilot controls (T-127 autopilot block)", () => {
  it("controls.ts mounts an autopilot block with policy chips, alpha-rho pad, budgets / interval", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/data-section=["']autopilot["']/);
    expect(src).not.toMatch(/data-section=["']controller["']/);

    for (const policy of ["damped_sw", "rollout", "constant"] as const) {
      expect(
        src,
        `expected policy chip data-policy="${policy}"`,
      ).toMatch(new RegExp(`data-policy=["']${policy}["']`));
    }

    expect(src).toMatch(/id=["']alpha-rho-pad["']/);

    for (const id of [
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

  it("react/studioLogic.ts mounts separate orders and spoilage charts (T-153)", () => {
    const layout = readFileSync(LAYOUT_TS, "utf8");
    const tuningDrawer = readFileSync(TUNING_DRAWER_TS, "utf8");
    const logic = readFileSync(LOGIC_TS, "utf8");
    expect(logic).toMatch(/renderControllerOrders\(\s*els\.controllerOrders/);
    expect(logic).toMatch(/renderWasteBars\(\s*els\.spoil/);
    expect(logic).toMatch(/spoilFocus/);
    expect(layout).toMatch(/id="chart-controller-orders"/);
    expect(layout).toMatch(/id="chart-spoil"/);
    expect(layout).not.toMatch(/id="chart-orders-spoilage"/);
    expect(tuningDrawer).toMatch(/id="chart-controller-orders-focus"/);
    expect(tuningDrawer).toMatch(/id="chart-spoil-focus"/);
    expect(tuningDrawer).toMatch(/data-plot="plot-controller-orders"/);
    expect(tuningDrawer).toMatch(/data-plot="plot-spoil"/);
    expect(tuningDrawer).not.toMatch(/id="chart-orders-spoilage-focus"/);
  });
});

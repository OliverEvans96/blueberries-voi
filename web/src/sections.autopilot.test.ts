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
const DAMPED_SW_DEMO_TS = join(HERE, "charts/dampedSwDemo.ts");

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

  it("autopilot plotIds use single damped_sw demo chart", () => {
    const autopilot = STUDIO_SECTIONS.find((s) => s.id === "autopilot");
    expect(autopilot).toBeDefined();
    const ids = autopilot!.plotIds;
    expect(ids).toEqual(["plot-damped-sw-demo"]);
    expect(ids).not.toContain("plot-controller-orders");
    expect(ids).not.toContain("plot-spoil");
    expect(ids).not.toContain("plot-age-comp");
  });
});

describe("Autopilot controls (T-127 autopilot block)", () => {
  it("controls.ts mounts an autopilot block with damped_sw + constant chips, alpha/rho sliders, n_particles / interval", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/data-section=["']autopilot["']/);
    expect(src).not.toMatch(/data-section=["']controller["']/);

    for (const policy of ["damped_sw", "constant"] as const) {
      expect(
        src,
        `expected policy chip data-policy="${policy}"`,
      ).toMatch(new RegExp(`data-policy=["']${policy}["']`));
    }
    expect(src).not.toMatch(/data-policy=["']rollout["']/);

    expect(src).toMatch(/type="range"[\s\S]*id=["']alpha["']/);
    expect(src).toMatch(/type="range"[\s\S]*id=["']rho["']/);
    expect(src).not.toMatch(/id=["']alpha-rho-pad["']/);

    for (const id of ["n_particles"] as const) {
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

describe("Autopilot chart wiring (damped_sw demo)", () => {
  it("ships dampedSwDemo chart module", () => {
    expect(
      existsSync(DAMPED_SW_DEMO_TS),
      "expected web/src/charts/dampedSwDemo.ts",
    ).toBe(true);
  });

  it("react/studioLogic.ts renders damped_sw demo on controller change and section visible", () => {
    const controls = readFileSync(CONTROLS_TS, "utf8");
    const logic = readFileSync(LOGIC_TS, "utf8");
    expect(logic).toMatch(/renderDampedSwDemo\(/);
    expect(logic).toMatch(/plot-damped-sw-demo/);
    expect(logic).toMatch(/onControllerChange[\s\S]*renderActiveFocusPlots/);
    expect(controls).toMatch(/id="chart-damped-sw-demo"/);
    expect(controls).toMatch(/data-plot="plot-damped-sw-demo"/);
    expect(controls).not.toMatch(/id="chart-controller-orders-focus"/);
    expect(controls).not.toMatch(/id="chart-spoil-focus"/);
  });
});

/**
 * T-099 RED: Controller section (nav key 8), controls knobs, plotIds,
 * react/studioLogic.ts chart mount wiring.
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

describe("Controller section registration (T-099)", () => {
  it("STUDIO_SECTIONS has controller as the 8th entry (nav key 8)", () => {
    expect(STUDIO_SECTIONS).toHaveLength(8);
    expect(STUDIO_SECTIONS[7]).toBeDefined();
    expect(STUDIO_SECTIONS[7]!.id).toBe("controller");
    expect(STUDIO_SECTIONS[7]!.label).toMatch(/^Controller$/i);
  });

  it("SectionId union in sections.ts includes controller", () => {
    const src = readFileSync(SECTIONS_TS, "utf8");
    const typeBlock = src.match(
      /export\s+type\s+SectionId\s*=([\s\S]*?);/,
    )?.[1];
    expect(typeBlock, "expected SectionId type alias").toBeDefined();
    expect(typeBlock).toMatch(/\|\s*"controller"/);
  });

  it("loadSection / saveSection accept controller and round-trip", () => {
    stubLocalStorage();
    saveSection("controller" as SectionId);
    expect(MEMORY_STORE.get(SECTION_STORAGE_KEY)).toBe("controller");
    expect(loadSection()).toBe("controller");
  });

  it("Belief and earlier sections remain intact at their indices", () => {
    expect(STUDIO_SECTIONS[0]?.id).toBe("play");
    expect(STUDIO_SECTIONS[6]?.id).toBe("belief");
    const belief = STUDIO_SECTIONS.find((s) => s.id === "belief");
    expect(belief).toBeDefined();
    expect(belief!.plotIds).toEqual(
      expect.arrayContaining(["plot-belief-age-marginal", "plot-belief-lg"]),
    );
  });

  it("controller plotIds include orders plot and reuse plot-inventory", () => {
    const controller = STUDIO_SECTIONS.find((s) => s.id === "controller");
    expect(controller).toBeDefined();
    const ids = controller!.plotIds;
    expect(ids).toContain("plot-controller-orders");
    expect(ids).toContain("plot-inventory");
  });
});

describe("Controller controls (T-099)", () => {
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

describe("Controller chart wiring (T-099)", () => {
  it("ships controllerOrders chart module", () => {
    expect(
      existsSync(CONTROLLER_ORDERS_TS),
      "expected web/src/charts/controllerOrders.ts",
    ).toBe(true);
  });

  it("react/studioLogic.ts mounts controller orders when that plot is visible", () => {
    const layout = readFileSync(LAYOUT_TS, "utf8");
    const logic = readFileSync(LOGIC_TS, "utf8");
    expect(logic).toMatch(/controllerOrders|renderControllerOrders/);
    expect(layout).toMatch(/data-plot=["']plot-controller-orders["']/);
    expect(logic).toMatch(/plotVisible\(\s*["']plot-controller-orders["']\s*\)/);
  });
});

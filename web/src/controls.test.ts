/**
 * T-127 tuning-dock: section controls data-section rename + content.
 */
// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import {
  DEFAULT_CONTROLLER_CONTROLS,
  formatSigmaPrecision,
  mountSectionControlsDom,
  precisionToSigma,
  SIGMA_MAX,
  SIGMA_MIN,
  SIGMA_PRECISION_MAX,
  sigmaToPrecision,
  type ControlsState,
} from "./controls";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "./mock/generate";
import { STUDIO_SECTIONS } from "./sections";
import type { SectionId } from "./sections";

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTROLS_TS = join(HERE, "controls.ts");

/** Tuning-dock tab sections wired by StudioLayout / studioLogic setSection(). */
const TUNING_DOCK_SECTIONS: SectionId[] = [
  "demand",
  "arrival",
  "physics",
  "logistics",
  "autopilot",
];

function baseState(): ControlsState {
  return {
    orderQty: 16,
    economics: { ...DEFAULT_ECONOMICS },
    config: { ...DEFAULT_SIM_CONFIG },
    configDirty: false,
    episodeDay: 3,
    pendingOrder: 0,
    schedule: {
      delivery_weekdays: [0, 2, 4],
      order_weekdays: [6, 1, 3],
      lead_time_days: 1,
      epoch: "2024-01-01",
    },
  };
}

describe("T-127 controls data-section rename", () => {
  it("uses new section ids and removes legacy play/belief/controller blocks", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).not.toMatch(/data-section=["']play["']/);
    expect(src).not.toMatch(/data-section=["']belief["']/);
    expect(src).not.toMatch(/data-section=["']controller["']/);
    expect(src).not.toMatch(/data-section=["']observation["']/);
    expect(src).toMatch(/data-section=["']autopilot["']/);
  });

  it("STUDIO_SECTIONS controlSection ids match mounted controls-block data-section values", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    for (const section of STUDIO_SECTIONS) {
      if (section.controlSection === "economics") continue;
      expect(
        src,
        `missing controls-block for ${section.id}`,
      ).toMatch(
        new RegExp(`data-section=["']${section.controlSection}["']`),
      );
    }
  });

  it("showSection reveals exactly the matching tuning-drawer controls block", () => {
    const host = document.createElement("div");
    host.className = "tuning-drawer-controls";
    const api = mountSectionControlsDom(
      host,
      baseState(),
      {
        onEconomicsChange: vi.fn(),
        onConfigChange: vi.fn(),
        onControllerChange: vi.fn(),
      },
      undefined,
      DEFAULT_CONTROLLER_CONTROLS,
    );

    for (const id of TUNING_DOCK_SECTIONS) {
      api.showSection(id);
      const blocks = host.querySelectorAll<HTMLElement>(".controls-block");
      for (const block of blocks) {
        const visible = block.dataset.section === id;
        expect(block.hidden, `${id} vs ${block.dataset.section}`).toBe(!visible);
      }
      expect(
        host.querySelector(`.controls-block[data-section="${id}"]:not([hidden])`),
      ).not.toBeNull();
    }
  });
});

describe("T-127 tuning-dock content", () => {
  it("moves sigma picking slider to demand and adds lead_time to logistics", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/id: "sigma"[\s\S]*group: "demand"/);
    expect(src).not.toMatch(/id: "sigma"[\s\S]*group: "physics"/);
    expect(src).toMatch(/id: "lead_time"[\s\S]*group: "logistics"/);
    expect(src).toMatch(/id="\$\{spec\.id\}"/);
  });

  it("physics block notes no separate gamma shape knob", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/No separate gamma shape knob post f-native migration/i);
  });

  it("autopilot block uses alpha-rho drag pad instead of separate sliders", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/id=["']alpha-rho-pad["']/);
    expect(src).not.toMatch(/id=["']alpha["'][\s\S]*type="range"/);
    expect(src).not.toMatch(/id=["']rho["'][\s\S]*type="range"/);
  });

  it("DEFAULT_CONTROLLER_CONTROLS defaults policy to damped_sw", () => {
    expect(DEFAULT_CONTROLLER_CONTROLS.policy).toBe("damped_sw");
  });

  it("sigma slider min/max are 0 (uniform sentinel) and SIGMA_PRECISION_MAX, not raw sigma bounds", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/id: "sigma"[\s\S]{0,300}min: 0/);
    expect(src).toMatch(/id: "sigma"[\s\S]{0,300}max: SIGMA_PRECISION_MAX/);
  });
});

describe("T-127 sigma slider is linear in 1/σ (precision), not σ", () => {
  it("sigmaToPrecision / precisionToSigma round-trip for typical σ", () => {
    for (const sigma of [0.05, 0.2, 0.5, 0.9, 1.5]) {
      const p = sigmaToPrecision(sigma);
      expect(precisionToSigma(p)).toBeCloseTo(sigma, 6);
    }
  });

  it("sigma <= 0 maps to the reserved uniform-picking sentinel precision 0", () => {
    expect(sigmaToPrecision(0)).toBe(0);
    expect(sigmaToPrecision(-1)).toBe(0);
  });

  it("precision 0 maps back to sigma 0 (uniform)", () => {
    expect(precisionToSigma(0)).toBe(0);
    expect(precisionToSigma(-5)).toBe(0);
  });

  it("precision is inversely related to sigma across the slider's range", () => {
    // Bigger slider value (precision) => smaller resulting sigma.
    const loP = sigmaToPrecision(SIGMA_MAX);
    const hiP = sigmaToPrecision(SIGMA_MIN);
    expect(hiP).toBeGreaterThan(loP);
    expect(hiP).toBeCloseTo(SIGMA_PRECISION_MAX, 6);
    expect(precisionToSigma(hiP)).toBeCloseTo(SIGMA_MIN, 6);
    expect(precisionToSigma(loP)).toBeCloseTo(SIGMA_MAX, 6);
  });

  it("formatSigmaPrecision shows 1/σ on the slider track, and uniform at the sentinel", () => {
    expect(formatSigmaPrecision(0)).toMatch(/uniform/i);
    expect(formatSigmaPrecision(sigmaToPrecision(0.35))).toBe("1/σ = 2.86");
  });

  it("moving the #sigma slider converts the raw (precision) value to σ before onConfigChange", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const onConfigChange = vi.fn();
    mountSectionControlsDom(
      host,
      baseState(),
      {
        onEconomicsChange: vi.fn(),
        onConfigChange,
        onControllerChange: vi.fn(),
      },
    );

    const sigmaInput = host.querySelector("#sigma") as HTMLInputElement;
    expect(sigmaInput).not.toBeNull();
    expect(sigmaInput.min).toBe("0");
    expect(sigmaInput.max).toBe(String(SIGMA_PRECISION_MAX));

    sigmaInput.value = "2";
    sigmaInput.dispatchEvent(new Event("input", { bubbles: true }));

    expect(onConfigChange).toHaveBeenCalledWith({ sigma: 0.5 });
    const label = host.querySelector("#val-sigma") as HTMLElement;
    expect(label.textContent).toBe("1/σ = 2.00");
    expect(host.querySelector("#picking-var-chart")).not.toBeNull();

    document.body.removeChild(host);
  });

  it("sigma slider position reflects config.sigma (converted to precision) on sync, not raw σ", () => {
    const host = document.createElement("div");
    const state = baseState();
    state.config = { ...state.config, sigma: 0.25 };
    const api = mountSectionControlsDom(
      host,
      state,
      {
        onEconomicsChange: vi.fn(),
        onConfigChange: vi.fn(),
        onControllerChange: vi.fn(),
      },
    );
    api.update(state);

    const sigmaInput = host.querySelector("#sigma") as HTMLInputElement;
    expect(Number(sigmaInput.value)).toBeCloseTo(1 / 0.25, 6);
    const label = host.querySelector("#val-sigma") as HTMLElement;
    expect(label.textContent).toBe("1/σ = 4.00");
  });
});

describe("T-127 tuning-dock content — demand controls", () => {
  it("demand section has no text-only projected μ preview (chart replaces it)", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).not.toMatch(/demand-preview-list/);
    expect(src).not.toMatch(/Next few days \(projected μ\)/);
  });

  it("embeds tuning chart host slots after demand sliders", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/chart-demand-host/);
    expect(src).toMatch(/chart-demand-forecast-host/);
    expect(src).toMatch(/picking-var-chart/);
  });

  it("tier badges show tier text only without info-tip triggers", () => {
    const src = readFileSync(CONTROLS_TS, "utf8");
    expect(src).toMatch(/tier-badge tier-badge--/);
    expect(src).not.toMatch(/tier-badge[\s\S]{0,120}info-tip-trigger/);
  });

  it("slider labels group the info glyph beside the label, value on the right", () => {
    const host = document.createElement("div");
    const api = mountSectionControlsDom(
      host,
      baseState(),
      {
        onEconomicsChange: vi.fn(),
        onConfigChange: vi.fn(),
        onControllerChange: vi.fn(),
      },
    );
    api.showSection("demand");
    const slider = host.querySelector("#sigma") as HTMLInputElement;
    expect(slider).not.toBeNull();
    const fieldLabel = slider.closest("label")?.querySelector(".field-label") as
      | HTMLElement
      | null;
    expect(fieldLabel).not.toBeNull();
    const main = fieldLabel.querySelector(".field-label-main");
    expect(main).not.toBeNull();
    expect(main!.querySelector(".info-tip-trigger")).not.toBeNull();
    expect(main!.querySelector("#val-sigma")).toBeNull();
    expect(fieldLabel.querySelector("#val-sigma")).not.toBeNull();
  });
});

/**
 * Sim truth overlay toggle — DecisionRail switch UX (ADR 0125 / T-127 shell).
 */
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_SIM_CONFIG } from "./mock/generate";
import { DecisionRail } from "./react/DecisionRail";
import { SHOW_TRUTH_STORAGE_KEY } from "./showTruth";

const MEMORY_STORE = new Map<string, string>();

afterEach(() => {
  document.body.replaceChildren();
  document.body.classList.remove("studio--show-truth");
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

function renderRail(showTruth = false) {
  const onShowTruthChange = vi.fn();
  render(
    createElement(DecisionRail, {
      vm: {
        episode_day: 1,
        window_days: 90,
        config: DEFAULT_SIM_CONFIG,
      },
      showTruth,
      orderQty: 16,
      activeSection: "demand",
      onAdvance: () => undefined,
      onReset: () => undefined,
      onAutopilotPlay: () => undefined,
      onAutopilotPause: () => undefined,
      onSetObsScenario: () => undefined,
      onShowTruthChange,
      onOrderChange: () => undefined,
    }),
  );
  const btn = screen.getByRole("switch", { name: /true state/i });
  return { btn, onShowTruthChange };
}

describe("DecisionRail truth toggle", () => {
  it("starts off with aria-checked false and Off label", () => {
    stubLocalStorage();
    const { btn } = renderRail(false);

    expect(btn.getAttribute("aria-checked")).toBe("false");
    expect(btn.classList.contains("truth-toggle--on")).toBe(false);
    expect(btn.querySelector(".truth-toggle-text")?.textContent).toBe("Off");
  });

  it("click invokes onShowTruthChange with toggled value", () => {
    stubLocalStorage();
    const { btn, onShowTruthChange } = renderRail(false);

    fireEvent.click(btn);
    expect(onShowTruthChange).toHaveBeenLastCalledWith(true);
  });

  it("showTruth true on mount starts on", () => {
    stubLocalStorage();
    const { btn } = renderRail(true);

    expect(btn.getAttribute("aria-checked")).toBe("true");
    expect(btn.classList.contains("truth-toggle--on")).toBe(true);
    expect(btn.querySelector(".truth-toggle-text")?.textContent).toBe("On");
  });

  it("renders truth toggle in decision-rail-truth section", () => {
    stubLocalStorage();
    renderRail(false);

    const section = document.querySelector(".decision-rail-truth");
    expect(section).not.toBeNull();
    expect(section!.querySelector(".truth-toggle-label")?.textContent).toBe(
      "Sim truth overlay",
    );
    expect(MEMORY_STORE.has(SHOW_TRUTH_STORAGE_KEY)).toBe(false);
  });
});

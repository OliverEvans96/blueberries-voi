/**
 * Sim truth overlay toggle — mountPlayChrome switch UX (ADR 0125).
 */
// @vitest-environment jsdom
import { fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mountPlayChrome, type ControlsState } from "./controls";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "./mock/generate";
import { SHOW_TRUTH_STORAGE_KEY } from "./showTruth";

function sampleState(): ControlsState {
  return {
    orderQty: 16,
    economics: { ...DEFAULT_ECONOMICS },
    config: { ...DEFAULT_SIM_CONFIG },
    configDirty: false,
    episodeDay: 0,
    pendingOrder: 0,
    schedule: null,
  };
}

const noopCb = {
  onOrderChange: () => undefined,
  onAdvance: () => undefined,
  onReset: () => undefined,
};

const MEMORY_STORE = new Map<string, string>();

let cleanup: (() => void) | undefined;
afterEach(() => {
  cleanup?.();
  cleanup = undefined;
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

function mountWithApp(showTruth = false) {
  const app = document.createElement("div");
  app.id = "app";
  document.body.appendChild(app);
  const root = document.createElement("div");
  document.body.appendChild(root);
  const onShowTruthChange = vi.fn();
  const api = mountPlayChrome(
    root,
    sampleState(),
    { ...noopCb, onShowTruthChange },
    { showTruth, truthClassTarget: app },
  );
  cleanup = () => api.destroy();
  const btn = root.querySelector("#btn-show-truth") as HTMLButtonElement;
  return { app, root, btn, onShowTruthChange };
}

describe("mountPlayChrome truth toggle", () => {
  it("starts off with aria-checked false and Off label", () => {
    stubLocalStorage();
    const { app, btn } = mountWithApp(false);

    expect(btn.getAttribute("aria-checked")).toBe("false");
    expect(btn.classList.contains("truth-toggle--on")).toBe(false);
    expect(btn.querySelector(".truth-toggle-text")?.textContent).toBe("Off");
    expect(app.classList.contains("studio--show-truth")).toBe(false);
  });

  it("click toggles on then off and persists to localStorage", () => {
    stubLocalStorage();
    const { app, btn, onShowTruthChange } = mountWithApp(false);

    fireEvent.click(btn);
    expect(btn.getAttribute("aria-checked")).toBe("true");
    expect(btn.classList.contains("truth-toggle--on")).toBe(true);
    expect(btn.querySelector(".truth-toggle-text")?.textContent).toBe("On");
    expect(app.classList.contains("studio--show-truth")).toBe(true);
    expect(MEMORY_STORE.get(SHOW_TRUTH_STORAGE_KEY)).toBe("true");
    expect(onShowTruthChange).toHaveBeenLastCalledWith(true);

    fireEvent.click(btn);
    expect(btn.getAttribute("aria-checked")).toBe("false");
    expect(btn.classList.contains("truth-toggle--on")).toBe(false);
    expect(btn.querySelector(".truth-toggle-text")?.textContent).toBe("Off");
    expect(app.classList.contains("studio--show-truth")).toBe(false);
    expect(MEMORY_STORE.get(SHOW_TRUTH_STORAGE_KEY)).toBe("false");
    expect(onShowTruthChange).toHaveBeenLastCalledWith(false);
  });

  it("opts.showTruth true on mount starts on", () => {
    stubLocalStorage();
    const { app, btn } = mountWithApp(true);

    expect(btn.getAttribute("aria-checked")).toBe("true");
    expect(btn.classList.contains("truth-toggle--on")).toBe(true);
    expect(btn.querySelector(".truth-toggle-text")?.textContent).toBe("On");
    expect(app.classList.contains("studio--show-truth")).toBe(true);
  });

  it("renders dedicated truth-toggle-row below play buttons", () => {
    stubLocalStorage();
    const { root } = mountWithApp(false);

    const row = root.querySelector(".truth-toggle-row");
    expect(row).not.toBeNull();
    expect(row!.querySelector(".truth-toggle-label")?.textContent).toBe(
      "Sim truth overlay",
    );
    expect(root.querySelector(".btn-row-play")?.contains(row!)).toBe(false);
  });
});

/**
 * T-115 RED: Play chrome switch “Show true state” + studio--show-truth class.
 */
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { mountPlayChrome, type ControlsState } from "./controls";
import { DEFAULT_ECONOMICS, DEFAULT_SIM_CONFIG } from "./mock/generate";

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

afterEach(() => {
  document.body.replaceChildren();
  document.body.classList.remove("studio--show-truth");
});

describe("play chrome show-truth switch (T-115)", () => {
  it("mounts a switch named /show true state/i with aria-pressed from the flag", () => {
    const app = document.createElement("div");
    app.id = "app";
    document.body.appendChild(app);
    const root = document.createElement("div");
    document.body.appendChild(root);

    const onShowTruthChange = vi.fn();
    mountPlayChrome(root, sampleState(), {
      ...noopCb,
      onShowTruthChange,
    }, { showTruth: false, truthClassTarget: app });

    const sw = root.querySelector('[role="switch"]');
    expect(sw, "expected role=switch in play chrome").not.toBeNull();
    const name = `${sw!.getAttribute("aria-label") ?? ""} ${sw!.textContent ?? ""}`;
    expect(name).toMatch(/show true state/i);
    expect(sw!.getAttribute("aria-pressed")).toBe("false");
    expect(app.classList.contains("studio--show-truth")).toBe(false);
    expect(document.body.classList.contains("studio--show-truth")).toBe(false);
  });

  it("applies studio--show-truth on #app when the switch is on", () => {
    const app = document.createElement("div");
    app.id = "app";
    document.body.appendChild(app);
    const root = document.createElement("div");
    document.body.appendChild(root);

    mountPlayChrome(root, sampleState(), noopCb, {
      showTruth: true,
      truthClassTarget: app,
    });

    const sw = root.querySelector('[role="switch"]');
    expect(sw).not.toBeNull();
    expect(sw!.getAttribute("aria-pressed")).toBe("true");
    expect(app.classList.contains("studio--show-truth")).toBe(true);
  });
});

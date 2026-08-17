/**
 * T-127 (layout v3): OperatorBar — order quantity + Advance/Autopilot/Reset,
 * mounted at the bottom of the Secondary pane. Autopilot Play/Pause is a
 * single toggle switch (mirrors DecisionRail's .truth-toggle) instead of two
 * separate buttons.
 */
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";
import { OperatorBar } from "./OperatorBar";

function baseProps() {
  return {
    vm: {
      episode_day: 3,
      window_days: 90,
      config: DEFAULT_SIM_CONFIG,
    },
    onAdvance: vi.fn(),
    onReset: vi.fn(),
    onAutopilotPlay: vi.fn(),
    onAutopilotPause: vi.fn(),
    orderQty: 16,
    onOrderChange: vi.fn(),
  };
}

describe("OperatorBar (T-127 layout v3)", () => {
  it("renders Advance/Reset, an Autopilot toggle switch, and the order quantity control", () => {
    const props = baseProps();
    render(createElement(OperatorBar, props));

    expect(screen.getByRole("button", { name: /^advance$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reset/i })).toBeInTheDocument();
    const toggle = screen.getByRole("switch", { name: /autopilot/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect(toggle.querySelector(".autopilot-toggle-text")?.textContent).toBe(
      "Autopilot: Off",
    );
    expect(screen.getByLabelText(/order quantity/i)).toBeInTheDocument();
    expect(document.querySelector("#order-num")).toHaveValue(16);
    expect(document.querySelector("#order-range")).not.toBeNull();
  });

  it("updates order quantity when the slider moves", () => {
    const props = baseProps();
    render(createElement(OperatorBar, props));

    const slider = document.querySelector("#order-range") as HTMLInputElement;
    fireEvent.input(slider, { target: { value: "32" } });
    expect(props.onOrderChange).toHaveBeenCalledWith(32);
  });

  it("calls onAdvance / onReset / onAutopilotPlay / onAutopilotPause", () => {
    const props = baseProps();
    const { rerender } = render(createElement(OperatorBar, props));

    fireEvent.click(screen.getByRole("button", { name: /^advance$/i }));
    expect(props.onAdvance).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(props.onReset).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("switch", { name: /autopilot/i }));
    expect(props.onAutopilotPlay).toHaveBeenCalled();
    expect(props.onAutopilotPause).not.toHaveBeenCalled();

    rerender(createElement(OperatorBar, { ...props, autopilotRunning: true }));
    fireEvent.click(screen.getByRole("switch", { name: /autopilot/i }));
    expect(props.onAutopilotPause).toHaveBeenCalled();
  });

  it("toggle reflects autopilotRunning with on/off label + aria-checked", () => {
    const props = { ...baseProps(), autopilotRunning: true };
    render(createElement(OperatorBar, props));

    const toggle = screen.getByRole("switch", { name: /autopilot/i });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(toggle.classList.contains("autopilot-toggle--on")).toBe(true);
    expect(toggle.querySelector(".autopilot-toggle-text")?.textContent).toBe(
      "Autopilot: On",
    );
  });

  it("disables Advance + Autopilot toggle at episode end when not running", () => {
    const props = { ...baseProps(), vm: { ...baseProps().vm, episode_day: 90 } };
    render(createElement(OperatorBar, props));

    expect(screen.getByRole("button", { name: /^advance$/i })).toBeDisabled();
    expect(screen.getByRole("switch", { name: /autopilot/i })).toBeDisabled();
  });

  it("keeps the Autopilot toggle enabled at episode end while running, so it can still be paused", () => {
    const props = {
      ...baseProps(),
      vm: { ...baseProps().vm, episode_day: 90 },
      autopilotRunning: true,
    };
    render(createElement(OperatorBar, props));

    expect(screen.getByRole("button", { name: /^advance$/i })).toBeDisabled();
    expect(screen.getByRole("switch", { name: /autopilot/i })).not.toBeDisabled();
  });

  it("slider drag updates value via onOrderChange only — no extra side effects", () => {
    const props = baseProps();
    render(createElement(OperatorBar, props));
    const slider = document.querySelector("#order-range") as HTMLInputElement;
    fireEvent.input(slider, { target: { value: "32" } });
    expect(props.onOrderChange).toHaveBeenCalledTimes(1);
    expect(props.onOrderChange).toHaveBeenCalledWith(32);
  });
});

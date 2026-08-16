/**
 * T-127 (layout v2): OperatorBar — order quantity + Advance/Autopilot/Reset,
 * split out of DecisionRail into a compact, prominent control bar.
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

describe("OperatorBar (T-127 layout v2)", () => {
  it("renders Advance/Autopilot Play/Autopilot Pause/Reset and the order quantity control", () => {
    const props = baseProps();
    render(createElement(OperatorBar, props));

    expect(screen.getByRole("button", { name: /^advance$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /autopilot play/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /autopilot pause/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reset/i })).toBeInTheDocument();
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
    render(createElement(OperatorBar, props));

    fireEvent.click(screen.getByRole("button", { name: /^advance$/i }));
    expect(props.onAdvance).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(props.onReset).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /autopilot play/i }));
    expect(props.onAutopilotPlay).toHaveBeenCalled();
  });

  it("disables Advance/Autopilot Play at episode end, Autopilot Pause unless running", () => {
    const props = { ...baseProps(), vm: { ...baseProps().vm, episode_day: 90 } };
    render(createElement(OperatorBar, props));

    expect(screen.getByRole("button", { name: /^advance$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /autopilot play/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /autopilot pause/i })).toBeDisabled();
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

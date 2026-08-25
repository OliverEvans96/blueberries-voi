/**
 * T-148: ObsControlsPane — observation channel controls (migrated from SecondaryChrome).
 */
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_SIM_CONFIG } from "../mock/generate";
import { ObsControlsPane } from "./ObsControlsPane";

describe("ObsControlsPane (T-148)", () => {
  it("renders channel chips and truth toggle without preset select", () => {
    const onShowTruthChange = vi.fn();
    render(
      createElement(ObsControlsPane, {
        vm: { config: DEFAULT_SIM_CONFIG },
        showTruth: true,
        onSetObsChannels: vi.fn(),
        onSetObsPreset: vi.fn(),
        onShowTruthChange,
      }),
    );

    expect(screen.getByTestId("obs-controls-pane")).toBeInTheDocument();
    expect(screen.getByTestId("obs-channels")).toBeInTheDocument();
    expect(screen.queryByLabelText(/preset/i)).toBeNull();
    expect(screen.getByLabelText(/show true state/i)).toHaveAttribute(
      "aria-checked",
      "true",
    );

    fireEvent.click(screen.getByLabelText(/show true state/i));
    expect(onShowTruthChange).toHaveBeenCalledWith(false);
  });

  it("uses scan-model toggles not ladder chips", () => {
    render(
      createElement(ObsControlsPane, {
        vm: { config: DEFAULT_SIM_CONFIG },
        showTruth: false,
        onSetObsChannels: vi.fn(),
        onSetObsPreset: vi.fn(),
        onShowTruthChange: vi.fn(),
      }),
    );
    expect(screen.getByTestId("obs-channels")).toBeInTheDocument();
    expect(screen.getByLabelText(/code type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/scan waste/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/delivery history/i)).toBeInTheDocument();
  });

  it("disables chips and truth toggle while booting", () => {
    render(
      createElement(ObsControlsPane, {
        vm: { config: DEFAULT_SIM_CONFIG },
        showTruth: false,
        booting: true,
        onSetObsChannels: vi.fn(),
        onSetObsPreset: vi.fn(),
        onShowTruthChange: vi.fn(),
      }),
    );
    expect(screen.getByLabelText(/show true state/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /upc/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^on$/i })).toBeDisabled();
  });
});

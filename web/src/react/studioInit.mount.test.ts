/**
 * T-158: initStudio must mount section controls after tuning drawer portal exists.
 */
// @vitest-environment jsdom
import { act, render, waitFor, type RenderResult } from "@testing-library/react";
import { createElement, StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

describe("studio init mount order (T-158)", () => {
  let rendered: RenderResult | undefined;

  beforeEach(() => {
    vi.stubEnv("VITE_ENGINE_ADAPTER", "mock");
  });

  afterEach(async () => {
    await act(async () => {
      rendered?.unmount();
      rendered = undefined;
    });
    vi.unstubAllEnvs();
    document.body.innerHTML = "";
  });

  it("App + StrictMode boot leaves #section-controls in DOM", async () => {
    const rootEl = document.createElement("div");
    rootEl.id = "app";
    document.body.appendChild(rootEl);

    rendered = render(createElement(StrictMode, null, createElement(App)), {
      container: rootEl,
    });

    await waitFor(() => {
      expect(rootEl.querySelector("#section-controls")).not.toBeNull();
    });
    expect(rootEl.querySelector("#tuning-drawer")).not.toBeNull();
    const trigger = rootEl.querySelector("#tuning-drawer-trigger");
    expect(trigger).not.toBeNull();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    const dialog = rootEl.querySelector("dialog#tuning-drawer");
    expect(dialog?.hasAttribute("open")).toBe(false);
    expect(rootEl.dataset.studioInit).toBe("1");
  });
});

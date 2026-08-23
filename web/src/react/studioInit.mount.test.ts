/**
 * T-158: initStudio must mount section controls after tuning drawer portal exists.
 */
// @vitest-environment jsdom
import { render, waitFor } from "@testing-library/react";
import { createElement, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

describe("studio init mount order (T-158)", () => {
  let root: Root | null = null;

  beforeEach(() => {
    vi.stubEnv("VITE_ENGINE_ADAPTER", "mock");
  });

  afterEach(() => {
    root?.unmount();
    root = null;
    vi.unstubAllEnvs();
    document.body.innerHTML = "";
  });

  it("App + StrictMode boot leaves #section-controls in DOM", async () => {
    const rootEl = document.createElement("div");
    rootEl.id = "app";
    document.body.appendChild(rootEl);

    root = createRoot(rootEl);
    root.render(createElement(StrictMode, null, createElement(App)));

    await waitFor(() => {
      expect(rootEl.querySelector("#section-controls")).not.toBeNull();
    });
    expect(rootEl.querySelector("#tuning-drawer")).not.toBeNull();
    expect(rootEl.dataset.studioInit).toBe("1");
  });
});

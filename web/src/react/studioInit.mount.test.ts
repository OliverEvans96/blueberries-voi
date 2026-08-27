/**
 * T-158 / T-160: initStudio must mount section controls after tuning drawer portal exists.
 */
// @vitest-environment jsdom
import { act, render, waitFor, type RenderResult } from "@testing-library/react";
import { createElement, StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockAdapter } from "../mock/adapter";
import { App } from "../App";

describe.sequential("studio init mount order (T-158)", () => {
  let rendered: RenderResult | undefined;
  const originalInit = MockAdapter.prototype.init;

  beforeEach(() => {
    vi.stubEnv("VITE_ENGINE_ADAPTER", "mock");
  });

  afterEach(async () => {
    MockAdapter.prototype.init = originalInit;
    await act(async () => {
      rendered?.unmount();
      rendered = undefined;
    });
    vi.unstubAllEnvs();
    document.body.innerHTML = "";
  });

  it(
    "App + StrictMode boot leaves #section-controls in DOM",
    async () => {
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
    await waitFor(() => {
      expect(rootEl.querySelector('[data-testid="chart-loading-shell"]')).toBeNull();
    });
    await waitFor(() => {
      expect(rootEl.querySelector(".operator-bar[aria-busy='true']")).toBeNull();
    });
    expect(rootEl.querySelector('[data-studio-init="1"]')).not.toBeNull();
  },
    15000,
  );

  it(
    "keeps sidebar hosts populated while engine init is pending",
    async () => {
    const rootEl = document.createElement("div");
    rootEl.id = "app";
    document.body.appendChild(rootEl);

    let releaseInit: (() => void) | undefined;
    const initGate = new Promise<void>((resolve) => {
      releaseInit = resolve;
    });
    MockAdapter.prototype.init = vi.fn(async function (
      this: MockAdapter,
      ...args: Parameters<MockAdapter["init"]>
    ) {
      await initGate;
      return originalInit.apply(this, args);
    });

    rendered = render(createElement(StrictMode, null, createElement(App)), {
      container: rootEl,
    });

    await act(async () => {
      await Promise.resolve();
    });

    const obsHost = rootEl.querySelector("#obs-controls-pane-host");
    const eventsHost = rootEl.querySelector("#events-pane-host");
    expect(obsHost?.childElementCount).toBeGreaterThan(0);
    expect(eventsHost?.childElementCount).toBeGreaterThan(0);
    expect(
      rootEl.querySelector(
        "#events-pane-host [data-testid='events-loading-placeholder']",
      ),
    ).not.toBeNull();
    expect(
      rootEl.querySelector("#obs-controls-pane-host [data-booting='true']"),
    ).not.toBeNull();
    expect(rootEl.querySelector(".operator-bar[aria-busy='true']")).not.toBeNull();

    releaseInit?.();

    await waitFor(
      () => {
        expect(rootEl.querySelector(".operator-bar[aria-busy='true']")).toBeNull();
      },
      { timeout: 10000 },
    );
  },
    15000,
  );

  it("App mounts into #studio-slot without #app in document (T-160)", async () => {
    const slotEl = document.createElement("div");
    slotEl.id = "studio-slot";
    document.body.appendChild(slotEl);

    rendered = render(createElement(App), { container: slotEl });

    await waitFor(() => {
      expect(slotEl.querySelector("#section-controls")).not.toBeNull();
    });
    expect(slotEl.querySelector('[data-studio-init="1"]')).not.toBeNull();
  });
});

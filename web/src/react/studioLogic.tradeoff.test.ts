/**
 * T-151 (E): belief-column tradeoff Curve/Histogram tab toggle.
 */
// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { fireEvent, render } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { initStudio } from "./studioLogic";
import { StudioLayout } from "./StudioLayout";

const HERE = dirname(fileURLToPath(import.meta.url));
const LOGIC_TS = join(HERE, "studioLogic.ts");
const LAYOUT_TS = join(HERE, "StudioLayout.tsx");

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

function tradeoffHostVisible(el: HTMLElement | null): boolean {
  if (!el) return false;
  return !el.hidden && el.style.display !== "none";
}

describe("belief column tradeoff toggle wiring (T-151 E)", () => {
  const logicSrc = stripComments(readFileSync(LOGIC_TS, "utf8"));
  const layoutSrc = stripComments(readFileSync(LAYOUT_TS, "utf8"));

  it("StudioLayout declares belief-tradeoff tab strip with data-tradeoff-tab", () => {
    expect(layoutSrc).toMatch(/belief-tradeoff-tabs/);
    expect(layoutSrc).toMatch(/data-tradeoff-tab="curve"/);
    expect(layoutSrc).toMatch(/data-tradeoff-tab="histogram"/);
    expect(layoutSrc).toMatch(/aria-label="Tradeoff view"/);
  });

  it("studioLogic wires tradeoff tabs imperatively", () => {
    expect(logicSrc).toMatch(/function wireTradeoffTabs/);
    expect(logicSrc).toMatch(/function syncTradeoffTabs/);
    expect(logicSrc).toMatch(/function setTradeoffTab/);
    expect(logicSrc).toMatch(/wireTradeoffTabs\(\)/);
    expect(logicSrc).toMatch(/\.belief-tradeoff-tabs \[data-tradeoff-tab\]/);
  });

  it("renderTradeoffBeliefColumn renders only the active tradeoff chart", () => {
    expect(logicSrc).toMatch(/function renderTradeoffBeliefColumn/);
    expect(logicSrc).toMatch(/tradeoffTab\s*===\s*["']curve["']/);
    expect(logicSrc).toMatch(/renderTradeoffCurve\(\s*els\.tradeoffCurve/);
    expect(logicSrc).toMatch(/renderTradeoffHistogram\(\s*els\.tradeoffHistogram/);
  });
});

describe("belief column tradeoff toggle interaction (T-151 E)", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_ENGINE_ADAPTER", "mock");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    document.body.innerHTML = "";
  });

  function mountStudio(): HTMLElement {
    const app = document.createElement("div");
    app.id = "app";
    document.body.appendChild(app);
    render(createElement(StudioLayout), { container: app });
    initStudio(app);
    return app;
  }

  it("shows curve and hides histogram by default", () => {
    const app = mountStudio();
    const curve = app.querySelector("#tradeoff-curve-host") as HTMLElement;
    const hist = app.querySelector("#tradeoff-histogram-host") as HTMLElement;
    expect(tradeoffHostVisible(curve)).toBe(true);
    expect(tradeoffHostVisible(hist)).toBe(false);
    expect(
      app.querySelector('.belief-tradeoff-tabs [data-tradeoff-tab="curve"]'),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("clicking Histogram tab shows histogram and hides curve", () => {
    const app = mountStudio();
    const curve = app.querySelector("#tradeoff-curve-host") as HTMLElement;
    const hist = app.querySelector("#tradeoff-histogram-host") as HTMLElement;
    const histTab = app.querySelector(
      '.belief-tradeoff-tabs [data-tradeoff-tab="histogram"]',
    ) as HTMLButtonElement;

    fireEvent.click(histTab);

    expect(tradeoffHostVisible(curve)).toBe(false);
    expect(tradeoffHostVisible(hist)).toBe(true);
    expect(histTab).toHaveAttribute("aria-selected", "true");
    expect(
      app.querySelector('.belief-tradeoff-tabs [data-tradeoff-tab="curve"]'),
    ).toHaveAttribute("aria-selected", "false");
  });

  it("clicking Curve tab restores curve visibility", () => {
    const app = mountStudio();
    const curve = app.querySelector("#tradeoff-curve-host") as HTMLElement;
    const hist = app.querySelector("#tradeoff-histogram-host") as HTMLElement;
    const curveTab = app.querySelector(
      '.belief-tradeoff-tabs [data-tradeoff-tab="curve"]',
    ) as HTMLButtonElement;
    const histTab = app.querySelector(
      '.belief-tradeoff-tabs [data-tradeoff-tab="histogram"]',
    ) as HTMLButtonElement;

    fireEvent.click(histTab);
    fireEvent.click(curveTab);

    expect(tradeoffHostVisible(curve)).toBe(true);
    expect(tradeoffHostVisible(hist)).toBe(false);
    expect(curveTab).toHaveAttribute("aria-selected", "true");
  });
});

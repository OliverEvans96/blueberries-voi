/**
 * Info-tip portal — React glyph + host-hover tooltips escape overflow.
 */
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { INFO_TIP_BUBBLE_Z_INDEX, initInfoTipPortal } from "../infoTipPortal";
import { infoTipHtml } from "../infoTip";
import { HostHoverTip } from "./HostHoverTip";
import { InfoTip } from "./InfoTip";
import { StudioLayout } from "./StudioLayout";

const INFO_TIP_CSS = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/infoTip.css"),
  "utf8",
);

function mountPortalRoot(): HTMLElement {
  const root = document.createElement("div");
  root.className = "bv-studio-portal-root";
  document.body.appendChild(root);
  return root;
}

/** Stub matchMedia so `(hover: none)` reports the given touch/mouse state. */
function stubHover(hasHover: boolean): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: query === "(hover: none)" ? !hasHover : hasHover,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  );
}

describe("InfoTip portal", () => {
  afterEach(() => {
    document.body.innerHTML = "";
    vi.unstubAllGlobals();
  });

  it("tapping the glyph toggles the tip open/closed on a no-hover (touch) device", () => {
    stubHover(false);
    const portalRoot = mountPortalRoot();
    render(createElement(InfoTip, null, "Tap-toggle tooltip"));

    const trigger = screen.getByRole("button", { name: /more information/i });
    fireEvent.click(trigger);
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).not.toBeNull();

    fireEvent.click(trigger);
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).toBeNull();
  });

  it("closes an open tip on an outside tap", () => {
    stubHover(false);
    const portalRoot = mountPortalRoot();
    render(createElement(InfoTip, null, "Outside tap closes"));

    fireEvent.click(screen.getByRole("button", { name: /more information/i }));
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).not.toBeNull();

    fireEvent.pointerDown(document.body);
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).toBeNull();
  });

  it("closes an open tip when tapping the bubble on touch devices", () => {
    stubHover(false);
    const portalRoot = mountPortalRoot();
    render(createElement(InfoTip, null, "Bubble tap closes"));

    fireEvent.click(screen.getByRole("button", { name: /more information/i }));
    const bubble = portalRoot.querySelector(".info-tip-bubble--portaled");
    expect(bubble).not.toBeNull();

    fireEvent.pointerDown(bubble!);
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).toBeNull();
  });

  it("a click does not close a hover-opened tip on a device with real hover", () => {
    stubHover(true);
    const portalRoot = mountPortalRoot();
    render(createElement(InfoTip, null, "Hover-only tooltip"));

    const trigger = screen.getByRole("button", { name: /more information/i });
    fireEvent.mouseEnter(trigger);
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).not.toBeNull();

    fireEvent.click(trigger);
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).not.toBeNull();
  });

  it("portals the glyph tooltip bubble on hover", () => {
    const portalRoot = mountPortalRoot();
    render(createElement(InfoTip, null, "Portal tooltip body"));

    const trigger = screen.getByRole("button", { name: /more information/i });
    fireEvent.mouseEnter(trigger);

    const bubble = portalRoot.querySelector(".info-tip-bubble--portaled");
    expect(bubble).not.toBeNull();
    expect(bubble).toHaveTextContent("Portal tooltip body");
    expect(bubble).toHaveStyle({ position: "fixed" });
    expect(bubble).toHaveStyle({ zIndex: String(INFO_TIP_BUBBLE_Z_INDEX) });
  });

  it("HostHoverTip shows a portaled bubble on host hover without an i glyph", () => {
    const portalRoot = mountPortalRoot();
    render(
      createElement(
        HostHoverTip,
        { tip: "Gear settings help" },
        createElement("button", { type: "button" }, "Settings"),
      ),
    );

    expect(screen.queryByRole("button", { name: /more information/i })).toBeNull();
    fireEvent.mouseEnter(screen.getByRole("button", { name: /settings/i }));

    const bubble = portalRoot.querySelector(".info-tip-bubble--portaled");
    expect(bubble).not.toBeNull();
    expect(bubble).toHaveTextContent("Gear settings help");
  });

  it("title bar gear and engine status use host-hover tips, not adjacent i-glyphs", () => {
    mountPortalRoot();
    const { container } = render(createElement(StudioLayout));
    const actions = container.querySelector(".title-bar-actions");
    expect(actions).not.toBeNull();

    const triggers = actions!.querySelectorAll(".info-tip-trigger");
    expect(triggers.length).toBe(0);

    expect(actions!.querySelector("#tuning-drawer-trigger")).not.toBeNull();
    expect(actions!.querySelector("#engine-status")).not.toBeNull();
  });

  it("infoTip.css hides inline vanilla bubbles until portaled", () => {
    expect(INFO_TIP_CSS).toMatch(
      /\.info-tip > \.info-tip-bubble\s*\{[^}]*display:\s*none/,
    );
  });

  it("infoTip.css enables pointer events on portaled bubbles", () => {
    expect(INFO_TIP_CSS).toMatch(
      /\.info-tip-bubble--portaled\s*\{[^}]*pointer-events:\s*auto/,
    );
  });

  it("infoTip.css stacks portaled bubbles above the tuning drawer", () => {
    expect(INFO_TIP_CSS).toMatch(
      /\.info-tip-bubble--portaled\s*\{[^}]*z-index:\s*1300/,
    );
    expect(INFO_TIP_BUBBLE_Z_INDEX).toBeGreaterThan(1200);
  });

  it("initInfoTipPortal portals vanilla infoTipHtml triggers on hover", () => {
    const portalRoot = mountPortalRoot();
    const host = document.createElement("div");
    host.innerHTML = infoTipHtml("Vanilla portal tooltip");
    document.body.appendChild(host);

    const cleanup = initInfoTipPortal(document);
    const trigger = host.querySelector(".info-tip-trigger") as HTMLElement;
    fireEvent.pointerOver(trigger, { relatedTarget: null });

    const bubble = portalRoot.querySelector(".info-tip-bubble--portaled");
    expect(bubble).not.toBeNull();
    expect(bubble).toHaveTextContent("Vanilla portal tooltip");

    cleanup();
  });

  it("ignores touch pointerover/pointerout, using tap-to-toggle instead", () => {
    stubHover(false);
    const portalRoot = mountPortalRoot();
    const host = document.createElement("div");
    host.innerHTML = infoTipHtml("Touch vanilla tooltip");
    document.body.appendChild(host);

    const cleanup = initInfoTipPortal(document);
    const trigger = host.querySelector(".info-tip-trigger") as HTMLElement;

    fireEvent.pointerOver(trigger, { relatedTarget: null, pointerType: "touch" });
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).toBeNull();

    fireEvent.click(trigger);
    const bubble = portalRoot.querySelector(".info-tip-bubble--portaled");
    expect(bubble).not.toBeNull();
    expect(bubble).toHaveTextContent("Touch vanilla tooltip");

    fireEvent.click(trigger);
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).toBeNull();

    cleanup();
  });

  it("closes a vanilla tip when tapping its bubble on touch devices", () => {
    stubHover(false);
    const portalRoot = mountPortalRoot();
    const host = document.createElement("div");
    host.innerHTML = infoTipHtml("Bubble dismiss vanilla");
    document.body.appendChild(host);

    const cleanup = initInfoTipPortal(document);
    const trigger = host.querySelector(".info-tip-trigger") as HTMLElement;

    fireEvent.click(trigger);
    const bubble = portalRoot.querySelector(".info-tip-bubble--portaled");
    expect(bubble).not.toBeNull();

    fireEvent.pointerDown(bubble!);
    expect(portalRoot.querySelector(".info-tip-bubble--portaled")).toBeNull();

    cleanup();
  });
});

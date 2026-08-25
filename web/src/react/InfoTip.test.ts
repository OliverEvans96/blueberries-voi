/**
 * Info-tip portal — React glyph + host-hover tooltips escape overflow.
 */
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { initInfoTipPortal } from "../infoTipPortal";
import { infoTipHtml } from "../infoTip";
import { HostHoverTip } from "./HostHoverTip";
import { InfoTip } from "./InfoTip";
import { StudioLayout } from "./StudioLayout";

function mountPortalRoot(): HTMLElement {
  const root = document.createElement("div");
  root.className = "bv-studio-portal-root";
  document.body.appendChild(root);
  return root;
}

describe("InfoTip portal", () => {
  afterEach(() => {
    document.body.innerHTML = "";
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
});

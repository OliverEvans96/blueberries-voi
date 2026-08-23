/**
 * T-158 RED (qa): TuningDrawer — sim params right drawer.
 */
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { TuningDrawer } from "./TuningDrawer";

function renderDrawer() {
  return render(
    createElement(
      "div",
      { className: "bv-studio", "data-testid": "studio-scope" },
      createElement(TuningDrawer),
    ),
  );
}

function studioScope(): HTMLElement {
  return document.querySelector(".bv-studio") as HTMLElement;
}

function getDialog(): HTMLDialogElement | null {
  return document.querySelector("dialog.tuning-drawer");
}

function getTrigger(): HTMLButtonElement | null {
  return document.querySelector("#tuning-drawer-trigger");
}

function pressKey(key: string, target: EventTarget = studioScope()) {
  fireEvent.keyDown(target, { key, bubbles: true });
}

describe("TuningDrawer (T-158 AC-drawer)", () => {
  it("renders gear trigger with aria-controls and no open drawer by default", () => {
    renderDrawer();

    const trigger = getTrigger();
    expect(trigger).not.toBeNull();
    expect(trigger).toHaveAttribute("aria-label", "Simulation parameters");
    expect(trigger).toHaveAttribute("aria-controls", "tuning-drawer");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(getDialog()).toBeNull();
  });

  it("opens dialog with aria-modal on trigger click and syncs aria-expanded", () => {
    renderDrawer();

    fireEvent.click(getTrigger()!);
    const dialog = getDialog();
    expect(dialog).not.toBeNull();
    expect(dialog).toHaveAttribute("open");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("id", "tuning-drawer");
    expect(getTrigger()).toHaveAttribute("aria-expanded", "true");
  });

  it("closes on Escape and resets aria-expanded", () => {
    renderDrawer();
    fireEvent.click(getTrigger()!);
    expect(getDialog()).not.toBeNull();

    pressKey("Escape");
    expect(getDialog()).toBeNull();
    expect(getTrigger()).toHaveAttribute("aria-expanded", "false");
  });

  it("closes when close button is clicked", () => {
    renderDrawer();
    fireEvent.click(getTrigger()!);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(getDialog()).toBeNull();
  });

  it("renders five cluster tabs without observation", () => {
    renderDrawer();
    fireEvent.click(getTrigger()!);

    expect(
      document.querySelector('.tuning-dock-tabs [data-section="observation"]'),
    ).toBeNull();
    for (const section of [
      "demand",
      "arrival",
      "physics",
      "logistics",
      "autopilot",
    ]) {
      const tab = document.querySelector(
        `.tuning-dock-tabs [data-section="${section}"]`,
      );
      expect(tab, `missing tab ${section}`).not.toBeNull();
    }
  });

  it("switches cluster tab aria-selected on click", () => {
    renderDrawer();
    fireEvent.click(getTrigger()!);

    const arrivalTab = document.querySelector(
      '.tuning-dock-tabs [data-section="arrival"]',
    ) as HTMLButtonElement;
    fireEvent.click(arrivalTab);
    expect(arrivalTab).toHaveAttribute("aria-selected", "true");
  });

  it("mounts #section-controls inside drawer body", () => {
    renderDrawer();
    fireEvent.click(getTrigger()!);

    const controls = document.querySelector(
      "#section-controls.tuning-drawer-controls",
    );
    expect(controls).not.toBeNull();
    expect(getDialog()?.contains(controls!)).toBe(true);
  });

  it("keeps at most one tuning dialog in the DOM while open", () => {
    renderDrawer();
    fireEvent.click(getTrigger()!);
    fireEvent.click(
      document.querySelector(
        '.tuning-dock-tabs [data-section="logistics"]',
      ) as HTMLElement,
    );
    expect(document.querySelectorAll("dialog.tuning-drawer")).toHaveLength(1);
  });
});

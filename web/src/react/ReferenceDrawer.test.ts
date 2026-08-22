/**
 * T-126 RED (qa-refdrawer): consolidated ReferenceDrawer — glossary, shortcuts, VOI.
 */
// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SCENARIO_COPY } from "../scenarioCopy";
import { ReferenceDrawer } from "./ReferenceDrawer";

type VoiReferenceData = {
  generated_at: string;
  disclaimer: string;
  rows: { scenario: string; metric: string; value: number }[];
};

const GLOSSARY_TERMS = [
  "Observation scenario",
  ...(["P0", "P1", "F1", "F1s", "F2a", "F2"] as const).map(
    (id) => `${id} — ${SCENARIO_COPY[id].title}`,
  ),
  "Sim truth overlay",
  "Base-stock",
];

const SHORTCUT_KEYS = ["1–8", "← →", "↑ ↓", "?", "T"];

const SAMPLE_VOI: VoiReferenceData = {
  generated_at: "2024-06-01T12:00:00.000Z",
  disclaimer: "Demo reference only — not live VOI.",
  rows: [{ scenario: "P1", metric: "profit_lift", value: 12.34 }],
};

function renderDrawer() {
  return render(
    createElement(
      "div",
      { className: "bv-studio", "data-testid": "studio-scope" },
      createElement(ReferenceDrawer),
    ),
  );
}

function studioScope(): HTMLElement {
  return document.querySelector(".bv-studio") as HTMLElement;
}

function getDialog(): HTMLDialogElement | null {
  return document.querySelector("dialog.reference-drawer");
}

function getTabs() {
  return screen.getAllByRole("tab");
}

function pressKey(key: string, target: EventTarget = studioScope()) {
  fireEvent.keyDown(target, { key, bubbles: true });
}

describe("ReferenceDrawer (T-126 AC-refdrawer)", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          json: () => Promise.reject(new Error("missing")),
        } as Response),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders three header triggers and no open drawer by default", () => {
    renderDrawer();

    expect(
      screen.getByRole("button", { name: "Glossary" }),
    ).toHaveClass("reference-drawer-trigger", "reference-drawer-trigger--glossary");
    expect(
      screen.getByRole("button", { name: "VOI reference" }),
    ).toHaveClass("reference-drawer-trigger", "reference-drawer-trigger--voi");
    expect(
      screen.getByRole("button", { name: "Shortcuts" }),
    ).toHaveClass("reference-drawer-trigger", "reference-drawer-trigger--shortcuts");

    expect(getDialog()).toBeNull();
  });

  it("opens the drawer on the matching tab when a trigger is clicked", () => {
    renderDrawer();

    fireEvent.click(screen.getByRole("button", { name: "Glossary" }));
    const dialog = getDialog();
    expect(dialog).not.toBeNull();
    expect(dialog).toHaveAttribute("open");
    expect(dialog).toHaveAttribute("aria-label", "Studio reference");

    const tabs = getTabs();
    expect(tabs.map((t) => t.textContent)).toEqual([
      "Glossary",
      "VOI reference",
      "Shortcuts",
    ]);
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(tabs[1]).toHaveAttribute("aria-selected", "false");
    expect(tabs[2]).toHaveAttribute("aria-selected", "false");
    expect(screen.getByText("Observation scenario")).toBeInTheDocument();
    expect(screen.queryByText("Jump to studio section")).not.toBeInTheDocument();
  });

  it("opens on Shortcuts when the Shortcuts trigger is clicked", () => {
    renderDrawer();

    fireEvent.click(screen.getByRole("button", { name: "Shortcuts" }));
    const tabs = getTabs();
    expect(tabs[2]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Jump to studio section")).toBeInTheDocument();
    expect(screen.getByText("1–8")).toBeInTheDocument();
  });

  it("opens on VOI reference when the VOI trigger is clicked", async () => {
    renderDrawer();

    fireEvent.click(screen.getByRole("button", { name: "VOI reference" }));
    const tabs = getTabs();
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(document.querySelector(".voi-reference--loading")).not.toBeNull();
    await waitFor(() => {
      expect(
        screen.getByText("VOI reference data not available."),
      ).toBeInTheDocument();
    });
  });

  it("switches tab content without closing when an in-drawer tab is clicked", () => {
    renderDrawer();

    fireEvent.click(screen.getByRole("button", { name: "Glossary" }));
    fireEvent.click(screen.getByRole("tab", { name: "Shortcuts" }));

    expect(getDialog()).not.toBeNull();
    const tabs = getTabs();
    expect(tabs[2]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Toggle sim truth overlay (when focused)")).toBeInTheDocument();
    expect(screen.queryByText("Observation scenario")).not.toBeInTheDocument();
  });

  it("includes all glossary entries verbatim on the Glossary tab", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Glossary" }));

    const list = document.querySelector("dl.glossary-list");
    expect(list).not.toBeNull();
    for (const term of GLOSSARY_TERMS) {
      expect(screen.getByText(term)).toBeInTheDocument();
    }
  });

  it("includes all shortcut entries verbatim on the Shortcuts tab", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Shortcuts" }));

    for (const keys of SHORTCUT_KEYS) {
      expect(screen.getByText(keys)).toBeInTheDocument();
    }
    expect(screen.getByText("Open this help")).toBeInTheDocument();
  });

  it("shows VOI loading then success data when fetch succeeds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(SAMPLE_VOI),
        } as Response),
      ),
    );

    renderDrawer();
    fireEvent.click(screen.getByRole("button", { name: "VOI reference" }));
    expect(document.querySelector(".voi-reference--loading")).not.toBeNull();

    await waitFor(() => {
      expect(screen.getByText(SAMPLE_VOI.disclaimer)).toBeInTheDocument();
    });
    expect(screen.getByLabelText("VOI reference (demo)")).toBeInTheDocument();
    expect(document.querySelector("table.voi-reference-table")).not.toBeNull();
    expect(screen.getByText("P1")).toBeInTheDocument();
    expect(screen.getByText("profit_lift")).toBeInTheDocument();
    expect(screen.getByText("12.34")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/voi-reference.json");
  });

  it("shows VOI empty state when fetch fails", async () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("button", { name: "VOI reference" }));

    await waitFor(() => {
      expect(
        document.querySelector(".voi-reference.voi-reference--empty"),
      ).not.toBeNull();
    });
    expect(
      screen.getByText("VOI reference data not available."),
    ).toBeInTheDocument();
  });

  it("closes the drawer when Escape is pressed", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Glossary" }));
    expect(getDialog()).not.toBeNull();

    pressKey("Escape");
    expect(getDialog()).toBeNull();
  });

  it("closes the drawer when the close button is clicked", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Glossary" }));
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(getDialog()).toBeNull();
  });

  it("opens the Shortcuts tab when ? is pressed outside inputs", () => {
    renderDrawer();
    pressKey("?");
    expect(getDialog()).not.toBeNull();
    expect(screen.getByRole("tab", { name: "Shortcuts" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByText("Jump to studio section")).toBeInTheDocument();
  });

  it("toggles the drawer closed when ? is pressed while Shortcuts is active", () => {
    renderDrawer();
    pressKey("?");
    expect(getDialog()).not.toBeNull();

    pressKey("?");
    expect(getDialog()).toBeNull();
  });

  it("switches to Shortcuts when ? is pressed while another tab is active", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Glossary" }));
    pressKey("?");

    expect(getDialog()).not.toBeNull();
    expect(screen.getByRole("tab", { name: "Shortcuts" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("ignores ? when focus is in an input or textarea", () => {
    render(
      createElement(
        "div",
        null,
        createElement("input", { "data-testid": "probe-input" }),
        createElement(ReferenceDrawer),
      ),
    );
    const input = screen.getByTestId("probe-input");
    pressKey("?", input);
    expect(getDialog()).toBeNull();
  });

  it("keeps at most one dialog element in the DOM while open", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("button", { name: "Glossary" }));
    fireEvent.click(screen.getByRole("tab", { name: "VOI reference" }));
    fireEvent.click(screen.getByRole("tab", { name: "Shortcuts" }));

    expect(document.querySelectorAll("dialog.reference-drawer")).toHaveLength(1);
  });
});

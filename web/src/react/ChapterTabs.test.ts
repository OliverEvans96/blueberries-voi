/**
 * T-126 RED (qa-tabs): ChapterTabs horizontal command bar.
 */
// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { STUDIO_CHAPTERS } from "../chapters";
import { STUDIO_SECTIONS, type SectionId } from "../sections";
import { ChapterTabs } from "./ChapterTabs";

function sectionIndex(sectionId: SectionId): number {
  return STUDIO_SECTIONS.findIndex((s) => s.id === sectionId) + 1;
}

function renderChapterTabs(activeSection: SectionId = "demand") {
  const onSelectSection = vi.fn();
  render(
    createElement(ChapterTabs, { activeSection, onSelectSection }),
  );
  return { onSelectSection };
}

describe("ChapterTabs (T-126 AC-tabs)", () => {
  it("renders a tablist with three chapter groups and eight section tabs", () => {
    renderChapterTabs("demand");

    const tablist = screen.getByRole("tablist", { name: "Studio sections" });
    expect(tablist).toBeInTheDocument();
    expect(tablist.tagName).toBe("NAV");
    expect(tablist).toHaveClass("chapter-tabs");

    const tabs = within(tablist).getAllByRole("tab");
    expect(tabs).toHaveLength(STUDIO_SECTIONS.length);

    for (const chapter of STUDIO_CHAPTERS) {
      expect(screen.getByText(chapter.title)).toBeInTheDocument();

      const group = tablist.querySelector(
        `[data-chapter="${chapter.id}"]`,
      ) as HTMLElement;
      expect(group).not.toBeNull();
      expect(group).toHaveClass("chapter-tabs-group");

      const groupTabs = within(group).getAllByRole("tab");
      expect(groupTabs).toHaveLength(chapter.sectionIds.length);

      for (const sectionId of chapter.sectionIds) {
        const section = STUDIO_SECTIONS.find((s) => s.id === sectionId)!;
        const tab = group.querySelector(
          `[data-section="${sectionId}"]`,
        ) as HTMLElement;
        expect(tab).not.toBeNull();
        expect(tab).toHaveClass("chapter-tabs-tab");
        expect(within(tab).getByText(String(sectionIndex(sectionId)))).toHaveClass(
          "chapter-tabs-index",
        );
        expect(within(tab).getByText(section.label)).toHaveClass(
          "chapter-tabs-label",
        );
      }
    }
  });

  it("marks the active tab with aria-selected and shows only its blurb", () => {
    const activeId: SectionId = "demand";
    renderChapterTabs(activeId);

    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(8);

    for (const section of STUDIO_SECTIONS) {
      const tab = screen.getByRole("tab", { name: new RegExp(section.label) });
      const blurb = within(tab).getByText(section.blurb);
      expect(blurb).toHaveClass("chapter-tabs-blurb");

      if (section.id === activeId) {
        expect(tab).toHaveAttribute("aria-selected", "true");
        expect(blurb).not.toHaveAttribute("hidden");
      } else {
        expect(tab).toHaveAttribute("aria-selected", "false");
        expect(blurb).toHaveAttribute("hidden");
      }
    }
  });

  it("calls onSelectSection once when clicking a non-active tab", () => {
    const { onSelectSection } = renderChapterTabs("demand");

    const demandTab = screen.getByRole("tab", { name: /demand/i });
    fireEvent.click(demandTab);

    expect(onSelectSection).toHaveBeenCalledTimes(1);
    expect(onSelectSection).toHaveBeenCalledWith("demand");
  });

  it("does not throw when clicking the already-active tab", () => {
    const { onSelectSection } = renderChapterTabs("observation");

    const observationTab = screen.getByRole("tab", { name: /observation/i });
    expect(() => fireEvent.click(observationTab)).not.toThrow();
    expect(onSelectSection).toHaveBeenCalledWith("observation");
  });
});

import { STUDIO_CHAPTERS } from "../chapters";
import { STUDIO_SECTIONS, type SectionId } from "../sections";
import "../styles/chapterTabs.css";

export type ChapterTabsProps = {
  activeSection: SectionId;
  onSelectSection: (id: SectionId) => void;
};

function sectionIndex(sectionId: SectionId): number {
  return STUDIO_SECTIONS.findIndex((s) => s.id === sectionId) + 1;
}

export function ChapterTabs({ activeSection, onSelectSection }: ChapterTabsProps) {
  return (
    <nav className="chapter-tabs" role="tablist" aria-label="Studio sections">
      {STUDIO_CHAPTERS.map((chapter) => (
        <div key={chapter.id} className="chapter-tabs-group" data-chapter={chapter.id}>
          <div className="chapter-tabs-chapter-title">{chapter.title}</div>
          {chapter.sectionIds.map((sectionId) => {
            const section = STUDIO_SECTIONS.find((s) => s.id === sectionId)!;
            const isActive = section.id === activeSection;
            return (
              <button
                key={section.id}
                type="button"
                className="chapter-tabs-tab"
                role="tab"
                data-section={section.id}
                aria-selected={isActive}
                onClick={() => onSelectSection(section.id)}
              >
                <span className="chapter-tabs-index">{sectionIndex(section.id)}</span>
                <span className="chapter-tabs-label">{section.label}</span>
                <span
                  className="chapter-tabs-blurb"
                  hidden={section.id !== activeSection}
                >
                  {section.blurb}
                </span>
              </button>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

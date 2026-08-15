# T-126 — QA test map (tabs shard)

## Coverage of acceptance criteria

### AC-tabs

- Exports `ChapterTabsProps` and `ChapterTabs` importing `STUDIO_CHAPTERS` / `STUDIO_SECTIONS` — `web/src/react/ChapterTabs.test.ts` (import of `./ChapterTabs`) — currently failing: module `./ChapterTabs` does not exist
- Renders `<nav role="tablist" aria-label="Studio sections">` with exactly 8 `role="tab"` elements — `ChapterTabs.test.ts::renders a tablist with three chapter groups and eight section tabs` — currently failing: cannot resolve `./ChapterTabs`
- Chapter grouping via `data-chapter` wrappers and chapter titles — same test — currently failing: component missing
- Each tab shows 1-based index (`STUDIO_SECTIONS.findIndex + 1`), label, and blurb — same test + `marks the active tab with aria-selected and shows only its blurb` — currently failing: component missing
- Active tab `aria-selected="true"`, others `false`; inactive blurbs `hidden` — `marks the active tab with aria-selected and shows only its blurb` — currently failing: component missing
- Click non-active tab → `onSelectSection(id)` once — `calls onSelectSection once when clicking a non-active tab` — currently failing: component missing
- Click active tab does not throw (may re-invoke callback) — `does not throw when clicking the already-active tab` — currently failing: component missing

## Not covered by tests

- `ChapterTabs` does not attach global `keydown` listener / does not import `studioLogic.ts` — static import ban is enforceable only at implement/review; verify by grep in `ChapterTabs.tsx`
- `web/src/styles/chapterTabs.css` styling — visual/CSS assertions deferred to implement + merge; component tests assert structure and ARIA only

## Implementer contract (from tests)

| Surface | Value |
|---------|-------|
| Props | `ChapterTabsProps = { activeSection: SectionId; onSelectSection: (id: SectionId) => void }` |
| Root | `<nav className="chapter-tabs" role="tablist" aria-label="Studio sections">` |
| Chapter group | `<div className="chapter-tabs-group" data-chapter={chapter.id}>` + visible chapter title text |
| Tab | `<button type="button" className="chapter-tabs-tab" role="tab" data-section={section.id} aria-selected="true"\|"false">` |
| Index | `<span className="chapter-tabs-index">{STUDIO_SECTIONS.findIndex(...) + 1}</span>` |
| Label | `<span className="chapter-tabs-label">{section.label}</span>` |
| Blurb | `<span className="chapter-tabs-blurb" hidden={section.id !== activeSection}>{section.blurb}</span>` |

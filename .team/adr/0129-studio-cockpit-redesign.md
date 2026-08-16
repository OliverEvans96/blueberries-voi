# 0129. Studio cockpit redesign — horizontal command bar, two-pane grid, self-sized rail

STATUS: PROPOSED
DATE: 2026-08-15
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: T-126 — UX follow-up to T-124, live screenshot + Playwright audit at 1440x900
TIER: 1
MILESTONE: ENG-01 — interactive studio
RELATED: ADR [0086](./0086-m15-richobs-unobserved-masks.md), [0110](./0110-studio-obs-scenario-ladder.md),
[0123](./0123-lazy-obs-scenario-filter-caches.md), [0125](./0125-studio-show-truth-js-only.md),
[0128](./0128-studio-ux-information-architecture.md)

## Context

ADR 0128 / T-124 shipped a three-zone grid (store timeline | focus pane | decision rail) plus a
vertical `.section-nav` chapter list, a comprehension layer (Guided Paths, glossary, day inspector,
VOI reference stub), and a scenario availability map. A follow-up UX review — live screenshots at
1440x900 and Playwright interaction testing against `./scripts/studio.sh --wasm` — found the
mechanism ADR 0128 chose does not hold up on a real desktop screen, even though its information
architecture principles (one shell, no per-scenario layout forks, chapter grouping) are sound:

- The three-zone grid squeezes `.store` / `.section-nav` / `.focus-pane` / decision rail into
  ~230–380px columns on a normal desktop. Charts — the tool's entire value proposition — end up the
  smallest elements on the page while large margins sit unused either side
  (`web/src/react/StudioLayout.tsx`, `.studio-layout--three-zone` in `web/src/styles.css`).
- A full vertical column (`.section-nav`) is spent on 8 text links that fit a horizontal row.
- Every section's focus pane repeats an identical Guided Paths block + instructional paragraph
  before the section's actual chart appears.
- `DecisionRail` (`web/src/react/DecisionRail.tsx`) is stretched by the grid to match the store
  column's height, leaving dead space under its P&L card — the rail's content is a fixed size, the
  grid track is not.
- `VoiReferencePanel` (static reference stub) sits glued under the live Play chart, mixing "live sim
  state" with "canned reference doc" in the same scroll region.
- `DayInspector` occupies a permanent block above the store chart whether or not a day is hovered.
- Store charts are four stacked slivers (`#chart-sales`, `#chart-stockout`, `#chart-history`,
  `#chart-spoil`) simultaneously visible, each further starved of height by the narrow column.
- BUG: `.chart-unavailable-hatch` (`position: absolute; inset: 0`) has no positioned ancestor —
  `.chart-unavailable` lacks `position: relative` — so on scenario P0 the placeholder's decorative
  overlay escapes its own box and intercepts pointer events across the whole `.store` panel
  (confirmed via Playwright: a nav-button click was captured by the hatch element instead).
- BUG: clicking an observation-ladder chip did not reliably flip the visible active chip. Root cause
  traced (this ADR, not the original review's hypothesis) to
  `web/src/react/studioLogic.ts`'s `onSetObsScenario` handlers calling
  `projector.patchEngineState(snap)` (captured into `vm`) followed by an **uncaptured**
  `projector.setConfig({ obs_scenario: id })` call whose returned `ViewModel` is discarded. Because
  `patchEngineState` does not itself sync `this.config.obs_scenario` from the snapshot's
  `applied_config`, the `vm` actually rendered can retain the pre-switch scenario. The originally
  suspected culprit — a dead duplicate handler in `controls.ts` — was already removed in T-124; it is
  not the cause.

This ADR fixes the mechanism, not the principles. ADR 0128's IA decisions — one HTML shell for all
`ScenarioId` values, gating via `scenarioAvailability` inside fixed slots, chapter-grouped sections,
JS-only comprehension affordances, no new npm dependencies — **still hold** and are not revisited
here. Only the concrete grid/nav/rail mechanism changes.

## Decision

We will restructure `web/src/react/StudioLayout.tsx` and its supporting components into a "cockpit,
not brochure" layout, still a single shell with no per-scenario fork:

1. **Horizontal command bar, not a vertical nav column.** New `web/src/react/ChapterTabs.tsx`
   replaces `.section-nav`: Operate / Understand / Tune render as a segmented tab row (`role="tablist"`)
   under the insight strip, reclaiming a full column's width for charts. Section keyboard shortcuts
   1–8, arrows, remain owned by `studioLogic.ts`'s existing global `keydown` listener — unchanged.
2. **Two real content panes**, not three cramped columns: **Store** (always-on global view) and
   **Focus** (active section), each wide enough that its chart dominates the pane rather than being
   its smallest element. Grid breakpoints stay at the ADR 0128 values (1100px, 720px); only what
   happens at each tier changes (two-pane instead of three-zone; see Consequences).
3. **Self-sized decision rail.** The rail becomes a slim cockpit strip pinned top-right, sized to its
   own content (Run controls, ladder chips, truth toggle, P&L) rather than stretched by the grid
   track to match the Store pane's height.
4. **Promote charts, demote prose.** Guided Paths becomes a single header-level entry point instead
   of a block repeated in every section's focus pane; per-section instructional text trims to a
   one-line caption.
5. **One reference-drawer pattern.** New `web/src/react/ReferenceDrawer.tsx` consolidates
   `GlossaryDrawer`, `ShortcutHelp`, and `VoiReferencePanel` into a single header-triggered slide-over
   with an internal tab switcher (Glossary / VOI reference / Shortcuts), so static reference content
   never competes with live sim content in the same scroll region. `GlossaryDrawer.tsx`,
   `ShortcutHelp.tsx`, and `VoiReferencePanel.tsx` are deleted; their content and behavior (glossary
   entries, `?`/Escape handling, VOI stub fetch + disclaimer + empty state) move into
   `ReferenceDrawer.tsx` verbatim.
6. **Day Inspector as a floating tooltip.** `web/src/react/DayInspector.tsx` renders nothing when
   idle and a small tooltip anchored to the hovered timeline point when a day is hovered.
   `web/src/hoverLink.ts`'s hover pipeline is extended to carry cursor position (`clientX`/`clientY`),
   not just the resolved day index, so the tooltip can be positioned.
7. **Store charts get real height.** New `web/src/react/StoreChartTabs.tsx` tabs the four stacked
   store charts into two views — "Sales & stockouts" (`#chart-sales`, `#chart-stockout`) and "Age &
   spoilage" (`#chart-history`, `#chart-spoil`) — instead of stacking four slivers simultaneously.
   Both view containers stay mounted in the DOM at all times (visibility toggled via a `hidden`
   attribute, matching the existing `.focus-plot[hidden]` pattern); chart host ids never
   unmount/remount, so the imperative D3 renderers in `studioLogic.ts` keep working unchanged
   regardless of which tab is active.
8. **Fix the two interaction bugs** as part of this pass:
   - `.chart-unavailable` gains `position: relative`; `.chart-unavailable-hatch` gains
     `pointer-events: none` in addition to its existing `aria-hidden`, so the decorative overlay can
     never intercept clicks even if a future ancestor loses its positioning again.
   - `ViewModelProjector.patchEngineState` (`web/src/engine/projector.ts`) syncs
     `this.config.obs_scenario` from `snapshot.applied_config.obs_scenario` when present, so the
     `ViewModel` it returns is immediately correct without depending on a second, separately-captured
     `setConfig` call at the caller site. This keeps the fix scoped entirely to `projector.ts`; the
     (now redundant but harmless) `projector.setConfig({ obs_scenario: id })` calls in
     `studioLogic.ts` are left as-is by this ticket (cleanup, if any, is the merge task's call, not a
     required behavior change).

## Alternatives considered

- **Keep the vertical `.section-nav` column, just make it narrower** — rejected; any vertical nav
  column costs a full grid track regardless of width; a horizontal row costs a header row's height
  instead, which is the resource this design has to spend to make charts bigger.
- **Per-scenario layout forks** (e.g. hide unavailable-plot columns entirely on P0 instead of showing
  a placeholder) — rejected for the same reason ADR 0128 rejected it: forks multiply test surface and
  break keyboard muscle memory; `scenarioAvailability` gating inside fixed slots stays the mechanism.
- **Separate drawers per reference surface** (keep `GlossaryDrawer` / `ShortcutHelp` /
  `VoiReferencePanel` as three independent dialogs) — rejected; three separate header triggers with
  three separate dialog implementations is exactly the "repeated boilerplate per section" pattern
  this ticket exists to remove, and static reference content would keep competing for header space
  with the live insight strip.
- **Fix the obs-chip bug by having `studioLogic.ts` capture the discarded `setConfig` return value**
  (`vm = projector.setConfig(...)`) instead of fixing `projector.ts` — rejected for this ticket's
  concurrency plan: `studioLogic.ts` is owned by the `merge` task, which lands after all six
  component/bugfix shards; fixing it in `projector.ts`'s `patchEngineState` keeps the bugfix
  self-contained to one file/shard (`impl-obschip`) with an isolated regression test, and produces a
  strictly more correct `patchEngineState` (any future caller gets the synced scenario for free, not
  just this one call site).
- **Rewrite `DayInspector` as a browser-native `<dialog popover>` or use a floating-UI positioning
  library** — rejected; no new npm dependency (ADR 0128 / T-124 constraint carries over), plain
  inline `style` positioning from `clientX`/`clientY` is sufficient at this shell's scale.
- **Collapse Store + Focus into one column even on wide desktops** — rejected, unchanged from ADR
  0128's reasoning: the store timeline is the episode spine and needs its own always-visible pane.

## Consequences

Charts become the dominant visual element on a normal desktop; the rail no longer wastes vertical
space; static reference material stops competing with live state in-scroll; the two known
interaction bugs are fixed with regression tests. Cost: `StudioLayout.tsx` and `studioLogic.ts` gain
one more integration seam (`merge` task) that must correctly wire six new/changed components without
regressing keyboard shortcuts or the six-rung obs ladder; `hoverLink.ts`'s public handler signature
changes (`onDay(day, point)` instead of `onDay(day)`), which is a breaking change for its one caller
(`studioLogic.ts`, updated by `merge`). The 1100px/720px breakpoint values from ADR 0128 are kept
verbatim so this ADR does not reopen calibration of those thresholds — only what renders at each tier
changes (two-pane grid + self-sized rail replaces three-zone grid; single-column stack with the rail
placed after both content panes replaces the current bare `grid-template-columns: 1fr` collapse).
Automated coverage for the visual redistribution itself is CSS-source-level (regex assertions against
`web/src/styles.css`, following this repo's existing precedent in e.g. `web/src/main.stockout.test.ts`)
plus component-level DOM/structure assertions; full pixel-accurate visual regression is out of scope
(no new browser/E2E tooling is introduced by this ticket — the 1440x900 Playwright pass that produced
this diagnosis was a one-off manual UX review, not a new CI gate). Revisit this ADR if URL routing,
SCN-P2, or a live/citeable VOI panel ships (each would need its own ADR, not an incremental layout
tweak); until then this ADR supersedes ADR 0128 §2 (three-zone grid) and §5's Glossary/VOI/Shortcut
component boundaries only — ADR 0128's other decisions (gating mechanism, chapter metadata, staged
demand preview, comprehension-affordance JS-only constraint) are unaffected and remain in force.

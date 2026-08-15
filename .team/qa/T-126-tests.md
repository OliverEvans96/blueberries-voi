# T-126 QA — RED test map (refdrawer shard)

Tracks **qa-refdrawer** shard only (`web/src/react/ReferenceDrawer.test.ts`).

## AC-refdrawer — consolidated ReferenceDrawer

| Criterion | Test | Expected RED reason |
| --- | --- | --- |
| Three triggers, closed by default | `ReferenceDrawer.test.ts::renders three header triggers and no open drawer by default` | `ReferenceDrawer.tsx` missing |
| Trigger opens drawer on matching tab | `::opens the drawer on the matching tab when a trigger is clicked` | Component missing |
| Shortcuts trigger | `::opens on Shortcuts when the Shortcuts trigger is clicked` | Component missing |
| VOI trigger + loading/empty | `::opens on VOI reference when the VOI trigger is clicked` | Component missing |
| In-drawer tab switch | `::switches tab content without closing when an in-drawer tab is clicked` | Component missing |
| Glossary entries verbatim | `::includes all glossary entries verbatim on the Glossary tab` | Component missing |
| Shortcut entries verbatim | `::includes all shortcut entries verbatim on the Shortcuts tab` | Component missing |
| VOI fetch success path | `::shows VOI loading then success data when fetch succeeds` | Component missing |
| VOI fetch failure path | `::shows VOI empty state when fetch fails` | Component missing |
| Escape closes | `::closes the drawer when Escape is pressed` | Component missing |
| Close button | `::closes the drawer when the close button is clicked` | Component missing |
| `?` opens Shortcuts | `::opens the Shortcuts tab when ? is pressed outside inputs` | Component missing |
| `?` toggles closed on Shortcuts | `::toggles the drawer closed when ? is pressed while Shortcuts is active` | Component missing |
| `?` switches from other tab | `::switches to Shortcuts when ? is pressed while another tab is active` | Component missing |
| INPUT/TEXTAREA guard | `::ignores ? when focus is in an input or textarea` | Component missing |
| Single dialog | `::keeps at most one dialog element in the DOM while open` | Component missing |

## Coverage of acceptance criteria

- Three triggers + single drawer with `role="tablist"` / three `role="tab"` → `ReferenceDrawer.test.ts::renders three header triggers…` / `::opens the drawer on the matching tab…` — currently failing: module `./ReferenceDrawer` not found
- Trigger opens matching tab; in-drawer tabs switch without close → `::opens the drawer…`, `::opens on Shortcuts…`, `::opens on VOI reference…`, `::switches tab content…` — currently failing: module missing
- Glossary `GLOSSARY_ENTRIES` verbatim → `::includes all glossary entries verbatim…` — currently failing: module missing
- Shortcuts `SHORTCUTS` verbatim → `::includes all shortcut entries verbatim…` — currently failing: module missing
- VOI fetch `/voi-reference.json` loading/success/failure → `::shows VOI loading then success…`, `::shows VOI empty state…` — currently failing: module missing
- `?` / Escape keyboard handling → `::opens the Shortcuts tab when ?…`, `::toggles…`, `::switches to Shortcuts…`, `::ignores ?…`, `::closes the drawer when Escape…` — currently failing: module missing
- Close button → `::closes the drawer when the close button is clicked` — currently failing: module missing
- At most one dialog → `::keeps at most one dialog element…` — currently failing: module missing

## Not covered by tests

- Deletion of `GlossaryDrawer.tsx` / `ShortcutHelp.tsx` / `VoiReferencePanel.tsx` — implement shard responsibility; verify at merge.
- `web/src/styles/referenceDrawer.css` — no CSS-source-text test in this shard; styling verified by implement + visual review.
- `merge` call-site wiring in `StudioLayout.tsx` — AC-merge shard.

## RED proof

```bash
cd web && npm ci && npx vitest run src/react/ReferenceDrawer.test.ts
```

Expected: suite fails — `Failed to resolve import "./ReferenceDrawer"`.

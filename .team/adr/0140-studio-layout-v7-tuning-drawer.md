# 0140. Studio layout v7 — tuning drawer

STATUS: PROPOSED
DATE: 2026-08-23

## Context

ADR [0139](../adr/0139-studio-layout-v6.md) established layout v6: a three-column cockpit
(`metrics | belief | sidebar`) plus a full-width bottom tuning dock row. User review finds
the persistent tuning row competes with metrics and belief for vertical space; sim-parameter
editing is a secondary, intentional action rather than a always-on surface.

The reference drawer (T-127) proved a fixed-right `<dialog>` overlay pattern for glossary,
VOI reference, and shortcuts. The tuning dock content — cluster tabs, section controls,
and teaching plots — should use the same interaction model, opened via a gear icon beside
`#engine-status` in the title bar.

## Decision

We adopt **layout v7**:

1. **Grid** — single row only: `metrics | belief | sidebar`;
   `grid-template-areas: "metrics belief sidebar"`; `data-layout="v7"` on `#linked-charts`.
2. **Bottom tuning row removed** — `.cockpit-row--tuning` and inline tuning dock markup
   retired from `StudioLayout.tsx`.
3. **TuningDrawer** — new `TuningDrawer.tsx` + `tuningDrawer.css`, modeled on
   `ReferenceDrawer.tsx`:
   - Portal host `#tuning-drawer-host` in `.bv-studio-portal-root`.
   - Fixed-right `<dialog class="tuning-drawer">` with backdrop, Escape, close button,
     `aria-modal`.
   - Trigger: `#tuning-drawer-trigger` gear button in `.title-bar-actions` left of
     `#engine-status`.
   - Width: `min(40rem, 100vw)` so half-width teaching charts remain legible.
4. **Interior layout** — 2-column interleaved grid replacing `tuning-dock-columns`
   (2fr/3fr split): controls and paired `.focus-plot` charts in semantic slots
   (`.tuning-drawer-slot`, `.tuning-drawer-slot--full`); `mountSectionControlsDom()`
   and chart IDs unchanged.
5. **Keyboard** — section shortcuts (`1–7`, arrows) open the drawer if closed and switch
   section; `?` continues to open ReferenceDrawer only.
6. **Chart resize** — on drawer open, `requestAnimationFrame` (double-rAF if needed) triggers
   `renderActiveFocusPlots()` to avoid zero-width chart paint (T-127 regression).
7. **Drawer stacking** — opening tuning drawer closes reference drawer (and vice versa);
   tuning drawer z-index above reference if both ever visible.

## Alternatives considered

- **Keep bottom dock, collapse by default** — rejected: still consumes grid semantics;
  drawer is clearer intentional secondary surface.
- **Narrow reference-width drawer** — rejected: half-width D3 charts unreadable at 28rem.
- **Reorder controls DOM** — rejected: keep `controls.ts` mount API; CSS slots only.

## Consequences

- **Easier** — metrics and belief reclaim vertical space; cockpit default is outcomes-focused.
- **Harder** — `studioLogic.ts` focus pane, tab sync, and visual QA selectors churn;
  e2e must open drawer before section tab assertions.
- **Locked in** — `.cockpit-row--tuning`, `.tuning-dock-columns` layout retired;
  `tuningDock.css` cluster-tab styles migrate minimally to `tuningDrawer.css`.
- **Supersedes** — layout v6 bottom tuning row and `data-layout="v6"` grid areas.

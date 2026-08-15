# T-126 — RED test map (all shards)

## Coverage of acceptance criteria

### AC-hatch

- `.chart-unavailable` declares `position: relative` → `web/src/react/ChartUnavailable.test.ts::".chart-unavailable rule declares position: relative so hatch absolute inset is scoped"` — currently failing: `.chart-unavailable {…}` in `web/src/styles.css` has no `position: relative` declaration (hatch `position: absolute; inset: 0` escapes to nearest positioned ancestor)
- `.chart-unavailable-hatch` declares `pointer-events: none` → `web/src/react/ChartUnavailable.test.ts::".chart-unavailable-hatch rule declares pointer-events: none so overlay cannot intercept clicks"` — currently failing: `.chart-unavailable-hatch {…}` in `web/src/styles.css` has no `pointer-events: none` declaration
- `ChartUnavailable` DOM structure / `data-plot-id` / `data-unavailable` / `role` / `aria-label` unchanged → `web/src/react/ChartUnavailable.test.ts::"renders unchanged DOM markers for chartSlots consumers"` — currently passing (baseline guard; implement must not regress)
- T-124 placeholder rendering (role, hatch, caption, no D3 svg) → existing tests in same file — currently passing

### AC-dayinspector — floating hover tooltip

- `web/src/hoverLink.ts` exports `HoverPoint` and `LinkedHoverHandlers.onDay(day, point)` → `web/src/hoverLink.test.ts::invokes onDay with resolved day and { clientX, clientY } on pointermove over a chart svg` — currently failing: `attachLinkedHover` calls `onDay(day)` with one argument only; second arg `{ clientX, clientY }` is never passed
- `attachLinkedHover` clears with `(null, null)` on root pointerleave → `web/src/hoverLink.test.ts::invokes onDay with (null, null) when pointer leaves the linked region` — currently failing: leave handler calls `onDay(null)` with one argument only
- `dayFromClientX` / other exports unchanged → covered indirectly by pointermove test using real `dayFromClientX` math (no separate regression test; unchanged behavior assumed if move test resolves correct day index)
- `DayInspector` renders `null` when `day == null` → `web/src/react/DayInspector.test.ts::renders nothing when day is null (no idle empty-state block)` — currently failing: component renders `.day-inspector--empty` permanent block instead of `null`
- `DayInspector` renders `null` when `point == null` → `web/src/react/DayInspector.test.ts::renders nothing when point is null even if day is set` — currently failing: component ignores `point` prop and renders day content without tooltip positioning
- Positioned floating tooltip (`.day-inspector-tooltip`, `role="status"`, `data-day`, inline `left`/`top` from `point` + 12px offset) → `web/src/react/DayInspector.test.ts::renders a positioned tooltip with day stats and belief one-liner` and `::positions the tooltip from point.clientX/clientY with a +12px offset` — currently failing: no `.day-inspector-tooltip`, no `point` prop, no cursor positioning
- Stats content unchanged (sales, waste, stockout, order qty, belief one-liner) → `web/src/react/DayInspector.test.ts::renders a positioned tooltip with day stats and belief one-liner` — currently failing: missing tooltip wrapper/class; content may render but not as specified floating tooltip
- No-history fallback when day provided without matching row → `web/src/react/DayInspector.test.ts::shows the no-history fallback inside the tooltip when day has no matching row` — currently failing: renders `.day-inspector` block without `.day-inspector-tooltip` wrapper
- Default belief one-liner when `age_marginal` absent → `web/src/react/DayInspector.test.ts::uses the default belief one-liner when age_marginal is absent` — currently failing: belief text renders but `.day-inspector-tooltip` wrapper is missing

## Not covered by tests

- `web/src/styles/dayInspector.css` (new stylesheet) — CSS styling is merge/implement visual polish; component tests assert structure, role, and inline positioning only
- `studioLogic.ts` wiring to forward `HoverPoint` to `DayInspector` — owned by AC-merge shard; verify via integration tests updated in merge
- Playwright click-interception regression (manual UX review only; out of scope per spec) — verify by manual `./scripts/studio.sh --wasm` smoke after implement
- Other AC sections (`obschip`, `tabs`, `refdrawer`, `storetabs`, `merge`) — owned by sibling shards, not this qa worktree

## Chosen contracts (verbatim for implementer)

```typescript
// web/src/hoverLink.ts
export type HoverPoint = { clientX: number; clientY: number } | null;

export type LinkedHoverHandlers = {
  onDay: (day: HoverDay, point: HoverPoint) => void;
};

// web/src/react/DayInspector.tsx
export type DayInspectorProps = {
  day: number | null;
  point: HoverPoint;
  vm: ViewModel;
};

// Tooltip root class + positioning
// className="day-inspector day-inspector-tooltip"
// style.left  = `${point.clientX + 12}px`
// style.top   = `${point.clientY + 12}px`
```

## Assertion contract for implement (hatch)

Read `web/src/styles.css` and ensure:

1. `.chart-unavailable { … }` includes `position: relative` (whitespace-flexible; tested via `/position\s*:\s*relative\b/` against the rule block extracted by `cssRuleBlock(".chart-unavailable", css)`).
2. `.chart-unavailable-hatch { … }` includes `pointer-events: none` (tested via `/pointer-events\s*:\s*none\b/` against `cssRuleBlock(".chart-unavailable-hatch", css)`).

Do **not** change `ChartUnavailable.tsx` props, exports, or rendered attribute/class structure.

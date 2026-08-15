# T-126 — QA RED map (hatch shard)

## Coverage of acceptance criteria

### AC-hatch

- `.chart-unavailable` declares `position: relative` → `web/src/react/ChartUnavailable.test.ts::".chart-unavailable rule declares position: relative so hatch absolute inset is scoped"` — currently failing: `.chart-unavailable {…}` in `web/src/styles.css` has no `position: relative` declaration (hatch `position: absolute; inset: 0` escapes to nearest positioned ancestor)
- `.chart-unavailable-hatch` declares `pointer-events: none` → `web/src/react/ChartUnavailable.test.ts::".chart-unavailable-hatch rule declares pointer-events: none so overlay cannot intercept clicks"` — currently failing: `.chart-unavailable-hatch {…}` in `web/src/styles.css` has no `pointer-events: none` declaration
- `ChartUnavailable` DOM structure / `data-plot-id` / `data-unavailable` / `role` / `aria-label` unchanged → `web/src/react/ChartUnavailable.test.ts::"renders unchanged DOM markers for chartSlots consumers"` — currently passing (baseline guard; implement must not regress)
- T-124 placeholder rendering (role, hatch, caption, no D3 svg) → existing tests in same file — currently passing

## Not covered by tests

- Playwright click-interception regression (manual UX review only; out of scope per spec) — verify by manual `./scripts/studio.sh --wasm` smoke after implement
- Other AC sections (`obschip`, `tabs`, `refdrawer`, `dayinspector`, `storetabs`, `merge`) — owned by sibling shards, not this qa worktree

## Assertion contract for implement

Read `web/src/styles.css` and ensure:

1. `.chart-unavailable { … }` includes `position: relative` (whitespace-flexible; tested via `/position\s*:\s*relative\b/` against the rule block extracted by `cssRuleBlock(".chart-unavailable", css)`).
2. `.chart-unavailable-hatch { … }` includes `pointer-events: none` (tested via `/pointer-events\s*:\s*none\b/` against `cssRuleBlock(".chart-unavailable-hatch", css)`).

Do **not** change `ChartUnavailable.tsx` props, exports, or rendered attribute/class structure.

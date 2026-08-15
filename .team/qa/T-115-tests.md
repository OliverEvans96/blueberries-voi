# T-115 — acceptance criteria → tests (RED)

## Coverage of acceptance criteria

- Fresh load with empty `localStorage` key `blueberries-voi-studio-show-truth` has `showTruth === false`
  → `web/src/showTruth.test.ts::showTruth persistence (T-115) > loadShowTruth defaults to false when storage is empty`
  — currently failing: `web/src/showTruth.ts` is missing (`Cannot find module './showTruth'`). The sibling `ships showTruth.ts module` test fails on `existsSync` false.

- `saveShowTruth(true)` then `loadShowTruth()` returns true; stored value is exactly `"true"` or `"false"`
  → `… > saveShowTruth then loadShowTruth round-trips; stored values are exactly true/false strings`
  — currently failing: same missing module.

- `truthLots(false, lots) => []`; `truthLots(true, lots) => lots`
  → `… > truthLots(false, lots) is empty; truthLots(true, lots) returns the lots`
  — currently failing: same missing module.

- Belief heatmap draws `.truth-cross` / `.truth-lot` when lots are passed, and zero overlay nodes when `truthLots=[]`
  → `web/src/charts/beliefAgeCount.test.ts::beliefAgeCount truth overlay (T-115) > draws zero .truth-cross / .truth-lot when truthLots is empty`
  → `… > draws .truth-cross and .truth-lot when lots are passed`
  — currently **passing** (renderer already gates on the `truthLots` argument; implementer must keep this when wiring `truthLots(show, live_lots)`).

- Survival rug length 0 when gated off (`lots=[]`); `.truth-*` when lots passed
  → `web/src/charts/survival.test.ts::survival lot rug (T-115) > draws zero rug marks when lots is empty`
  — currently **passing** (empty `lots` already draws no `.lot-rug`).
  → `… > draws rug marks with a .truth-* class when lots are passed`
  — currently failing: rugs exist as `.lot-rug` with **no** `.truth-*` class.

- History lot circles length 0 when `d.lots` arrays are empty; `.truth-circle` when nonempty
  → `web/src/charts/history.test.ts::history lot circles (T-115) > draws zero .lot circles when history days have empty lots arrays`
  — currently **passing**.
  → `… > draws lot circles with a truth stroke class when lots are nonempty`
  — currently failing: `.lot` circles have fill only, no `.truth-circle`.

- Arrival-prior `age_at_receipt` marks length 0 when gated off; `.truth-*` when samples exist
  → `web/src/charts/arrivalPrior.test.ts::arrival prior receipt-age rug (T-115) > draws zero rug marks when history has no age_at_receipt / arrivals`
  — currently **passing**.
  → `… > draws rug marks with a .truth-* class when receipt-age samples exist`
  — currently failing: `.arrival-rug` lines have no `.truth-*` class.

- Inventory vs target uses Σ `lot_counts` from `belief_history` when show-truth is off, and `history[].lots` when on
  → `web/src/charts/inventoryTarget.test.ts::inventorySeries lots vs belief (T-115) > truth lots path: on_hand equals sum of lot n`
  — currently **passing** (`inventorySeries` still sums `d.lots`).
  → `… > belief path: on_hand equals Σ lot_counts for that day, not the truth lot sum`
  — currently failing: optional `inventorySeriesFromBelief` / `{ from: 'belief' }` is ignored; `on_hand` is 18 (lots) not 6.92 (Σ lot_counts).

- Age composition 0–2 / 3–5 / 6d+ from belief expected ages vs truth lots
  → `…::age composition lots vs belief (T-115) > truth lots path: 0–2 / 3–5 / 6d+ bands from lot tau and n`
  — currently failing: `ageCompositionSeries` is not exported (`typeof` undefined).
  → `… > belief path: bands from expected ages, not truth lots`
  — currently failing: neither `ageCompositionSeriesFromBelief` nor `ageCompositionSeries(..., { from: 'belief' })` exists.

- Projector `belief_history` length tracks the same rolling window as `history`; Snapshot/DayDelta fixtures omit `showTruth`
  → `web/src/engine/projector.test.ts::ViewModelProjector belief_history rolling window (T-115) > belief_history length tracks history after applySnapshot + applyDelta; payloads omit showTruth`
  — currently failing: `vm.belief_history` is not an array (`undefined`). Fixtures do not include `showTruth` (those `hasOwnProperty` checks pass before the length assertion).

- Play chrome switch `/show true state/i`, `role=switch`, `aria-pressed`, class `studio--show-truth` on `#app` iff on
  → `web/src/controls.showTruth.test.ts::play chrome show-truth switch (T-115) > mounts a switch named /show true state/i with aria-pressed from the flag`
  → `… > applies studio--show-truth on #app when the switch is on`
  — currently failing: no `[role="switch"]` after `mountPlayChrome`. Tests pass optional 4th arg `{ showTruth, truthClassTarget }` and `onShowTruthChange` on the callbacks object.

- Belief section blurb does **not** require the word “truth” when show-truth is off
  → `web/src/sections.belief.test.ts::Belief section contracts (T-090) > blurb mentions age×count belief and the age marginal (does not require the word truth)`
  — currently **passing** (supersedes always-match `/truth/`; still asserts age×count + marginal).

- No production edits under `crates/`, `src/blueberries_voi/simulator/`, or wasm adapters
  — not covered by a behavioural test; verify by diff (qa wrote tests only).

## Not covered by tests

- Wiring `main.ts` to call `truthLots(loadShowTruth(), vm.live_lots)` on every chart — covered indirectly once implementer uses the helpers; no source-order grep required by AC.
- Knowledge-scenario-specific “observed” marks — out of scope (backlog).

# Changelog

Plain-English notes of what shipped, for non-technical readers.

## 2026-08-16
- **Observation in the studio is now three independent toggles — POS, waste, and delivery detail — with named presets (P0 through F2) kept for comparisons; switching channels mid-episode still uses the same lazy catch-up replay as before** (T-128).
- **The studio cockpit now shows freshness over time with a truth overlay, a stacked freshness histogram by lot, sales-versus-demand with red stockout shading, and consolidated profit charts in the Economics pane — duplicate P&L sparklines were removed, the Events pane lists days newest-first with illustrative delivery temperature traces, tradeoff charts show mean waste and missed-sales lines, and the tuning dock has real sub-navigation with improved demand, arrival, physics, logistics, and autopilot controls** (T-127 round 2).
- **Fixed a crash that could occur when switching observation scenarios while the waste chart was hidden, and corrected a wording glitch that showed "1 units" instead of "1 unit" in the events log** (T-127 round 2 visual QA).
- **The studio now uses a fixed cockpit grid with always-visible belief, economics, events, and run panes, plus tradeoff forecast charts and a masked event log for your observation rung** (T-127).

- **The production freshness filter (C2 Algorithm A) now has a published timing and accuracy study wired to the real engine code — about 5.7 ms per day at a 20-lot store, well under the 500 ms budget, with near-perfect order recommendations on scripted tests** (T-C2-A).

## 2026-08-15

- **The store studio now uses a wider two-pane layout — charts are the focus, section switching is a horizontal bar under the header, run controls sit in a compact rail, and a Start here menu offers guided learning paths without repeating boilerplate in every section** (T-126).
- **The store studio now runs its day-by-day math in the browser through the native Rust engine — no separate server or in-browser Python install** (T-125).
- **The store studio is easier to scan: a top strip shows the day, delivery rhythm, knowledge rung, and profit; a sticky rail keeps Run controls, observation chips, truth toggle, and P&L visible while you explore any section** (T-124).
- **Charts and knobs now respect what each knowledge rung actually observes — spoilage stays hidden on books-only P0, arrival receipt detail unlocks on F2, and demand sliders preview the week profile without resetting the episode** (T-124).
- **The store simulator now runs its heavy day-by-day math in the native engine by default, while notebooks and batch studies still orchestrate runs from Python** (T-121 Wave E).

## 2026-08-14

- **On the in-browser store, the knowledge chips now change the belief heatmap for real, without changing the true lots on the shelf** (T-117).
- **The store now shows a red missed-sales chart under units sold so lost sales line up with the rest of the day hover** (T-116).
- **The live store simulator can use the native engine when that option is switched on, with the original simulator still the default** (T-110).
- **Studio charts now keep the whole store run, then stop at day 90 and ask you to Reset — including the offline mock engine, not only the live Python session** (T-112).
- **Knowledge chips now retarget what the store can see on the current run without Reset; Autopilot’s next order follows that choice, while physics and past orders stay the same** (T-113).
- **Studio now defaults to manager beliefs and a Show true state switch reveals sim truth in a consistent style** (T-115).

## 2026-08-13

- **Internal structure was cleaned up without changing scores or how the simulator, filter, or studio behave** (T-102).
- **In the studio you can Autopilot-play day by day with controller policy knobs and pause safely** (T-091, T-097–T-101).
- **The default store now orders for Monday / Wednesday / Friday deliveries with a calendar-shaped weekly demand pattern instead of every-day i.i.d. sales; prior citeable value-of-information numbers from the daily base case need to be regenerated** (T-076–T-088 / CAL-01).
- **The in-browser store simulator starts again — the engine worker now loads in a way the current browser runtime accepts, so Advance and Reset are no longer blocked at startup** (T-092).

- **The Belief heatmap now plots true age against count (no more two-day lot-index glitch), with a merged age chart above it so belief lines up with truth markers** (T-090).
- **In the studio you can choose among six observation levels—from books-only through age at receipt—each with a clear title and description, and Reset applies that choice so the live simulator only sees what that level is allowed to know** (T-089).
- **Shelf age reports now carry what we knew at receipt, and we removed Rao–Blackwellised in-store age marginalisation because in-store age learning was dropped — not because a simpler bootstrap was preferred** (T-068, T-069).
- **You can run the studio against a real local API and a real in-browser engine using a wheel built on your machine, with Advance and Reset working without fake data** (T-075).

## 2026-08-12 — ENG-01 dual-runtime / live simulator

- **You can interact with the live ordering simulator in the browser under dialed demo budgets, and developers can iterate on the same engine through a local API** (T-058).

## 2026-08-12 — Slice 2: local HTTP API for developers

- **Developers can now drive the same simulator engine over a local HTTP API** for
  iteration, without changing the browser demo path. This is a development host only —
  not a production multi-tenant service (T-052).

## 2026-08-12 — Slice 1: interactive engine in the browser

- **You can now run the interactive Python engine in a browser worker** under
  dialed demo budgets (lightweight particle and horizon caps), so the store
  simulator steps without a separate server for the demo path. Full production-scale
  in-tab runs and the developer HTTP API remain later work (T-048).
## 2026-08-12 — Exact filter likelihood speedups (same answers)

- **Age-learning from storewide sales and waste is much faster on the same math:** the
  filter still uses the exact pick-and-spoil likelihood, but skips repeated work on
  duplicate particles and uses a faster internal table, so the expensive knowledge
  columns finish in a fraction of the previous time without changing the numeric
  model (T-064–T-066).
## 2026-08-12 — Audit remediation (silent defaults)

- **Production comparison runs no longer quietly use conflicting order-rounding or a toy cold
  chain:** whole-case rounding follows one nearest-case rule, missing shipment inputs load the
  real cold-chain traces, dollar cost defaults sit in one documented place, full value-of-
  information runs refuse untuned service levels, and age-belief updates use the agreed
  iteration count — while bakeoff-only filter arms are clearly marked not for citation.
  Calibrated blueberry economics and citeable science VOI are still out of scope (T-042–T-044).

## 2026-08-12 — M3 value-of-information sweep

- **You can now compare store profit across knowledge levels and spoilage shapes:** the
  study reports both a percentage lift versus the least-informed books-only view and the
  matching dollar gap, with paired confidence intervals, including a check that age
  information adds essentially nothing when spoilage is memoryless. Browser packaging and
  “what if the model is wrong” honesty arms are still out of scope.

## 2026-08-12 — M2 close-out: controller and multi-scenario

- **The ordering controller milestone is complete:** you can run the full ladder of
  ordering rules under several information views (rich lot visibility, storewide sales
  only, and an age-blind baseline), with tuned service levels and the agreed safety
  checks, while age tracking stays on the simpler production model. No dollar
  value-of-information headlines and no Pyodide packaging / ENG-01 browser demo /
  WASM ship in this close-out (T-034).

## 2026-08-12 — M2 Wave 6 multi-scenario closed-loop + L remeasure

- **Ordering rules can now be compared under three different information views** — rich lot visibility, storewide sales only, and a simple age-blind baseline — with a short written report that also records how long product is lasting under the real controller, while age tracking stays on the simpler production model (T-033).

## 2026-08-12 — M2 Wave 5 ladder + automated safety gates

- **The five ordering baselines can now be scored end-to-end in one run** — constant order, age-blind baseline, survival-weighted rule, look-ahead improvement, and the tiny exact planner — with results saved under experiments, and profit claims refused unless the tuned service-level table is present (T-032).
- **Three automatic checks now fail the test suite if broken:** age-aware and age-blind orders match when aging is turned off, paired random streams stay synchronized for fair comparisons, and the look-ahead rule’s gap to the tiny exact planner is reported (T-032).

## 2026-08-12 — M2 Wave 4 rollout + toy DP certificate

- **Ordering can try one short look-ahead improvement step** around the survival-weighted base rule, scoring candidate orders over a shelf-life-scale horizon with a documented end-of-horizon salvage value, and paired random streams keep the comparison fair (T-030).
- **A tiny exact planner can compute the best possible value on a toy shelf** and report how far the look-ahead (or base) rule sits from that optimum, including a check that age-aware and age-blind rules share the same protection window when aging is turned off (T-031).

## 2026-08-12 — M2 Wave 3 α tuning

- **Each ladder ordering rule can now get a simulation-tuned service level (α)** from a shared-seed grid search that scores day/episode profit, with tuned values saved under experiments; profit claims that skip that tuned table are rejected (T-029).

## 2026-08-12 — M2 Wave 2 base policies

- **An honest age-blind baseline can place orders from total stock on hand** (plus what is already on order), with a documented expected-spoilage correction, so the ladder has a fair competitor that does not peek at lot ages (T-027).
- **A damped survival-weighted ordering rule is available** that looks at age-aware effective inventory, applies a default 0.8 damping factor, and returns whole-case orders — the base stock policy the rest of the controller ladder builds on (T-028).

## 2026-08-12 — M2 Wave 1 controller foundations

- **Policies can read a shared shelf belief** built from the live age filter or from known true lot ages, including an effective on-hand figure that accounts for stock already on order (T-023).
- **A closed-loop day driver can ask a policy for each day’s order**, keep the same store physics and random streams as the open-loop simulator, and take shipment traces as an input instead of reading cold-chain files by itself (T-024).
- **Day and episode profit can be scored** from sales, waste, and lost sales only — holding cost is left out of that score, matching the agreed accounting rule (T-025).
- **Orders can be rounded to whole cases** with a documented nearest-case rule, and a constant daily order policy is available as the ladder’s simple baseline (T-026).

## 2026-08-12 — M1.5 filter complete across data-availability rungs

- **Production age tracking now uses the simpler mean-field per-lot belief** confirmed
  by the Stage C check: the live filter updates each lot’s age belief independently when
  only storewide sales and shrink are known, keeps the detailed per-lot path when
  lot IDs are visible, and no longer switches models just because more lots are
  on the shelf (T-021).

- **Delivery days now carry a pack date**, so the pack-date age check can tighten
  beliefs the way it was designed to — that rung is no longer blocked waiting
  on missing receipt metadata (T-019).

- **The age filter can now run honestly across the settled data-availability
  rungs:** each rung only observes what that scenario allows from the rich daily
  store log, and the filter’s likelihood matches the same physics the simulator
  uses. Under defaults, P0 and P1 still do not tighten arrival-age beliefs (an
  honest negative, not a papered-over pass); at M1.5 close-out F2a was still
  blocked on missing pack-date metadata (cleared later the same day by T-019
  above); F2 passes, and the oracle ladder shows F2 much closer to known true
  ages than P1. (T-018)

- Long-dwell store settings that create more overlapping lots no longer crash the
  age filter: it keeps the accurate joint model when memory allows, and switches
  to the approved lighter fallback with a clear record of why when the budget
  would be exceeded — without quietly dropping lots (T-015).
- When lot IDs are visible on sales or shrink, the filter now uses that
  per-lot detail to update each lot’s age belief, without letting one lot’s
  signal wrongly dominate another (T-014).
- When a delivery includes a pack date or a measured age at receipt, the filter now
  starts that new lot with a tighter age belief instead of the broad cold-chain
  default (T-013).
- Checked whether a simpler per-lot age belief is close enough to the full
  joint belief on small toy shelves: it passed the agreed accuracy gates, so
  we recommend (but have not yet board-confirmed) switching to that simpler
  form for production work (T-020; evidence-only MF Stage C).
- Built the first working inventory simulator and age-tracking filter for the blueberry
  study, including real cold-chain temperature traces and a bakeoff that chose the
  tractable full joint age model for production at the small live-cohort counts we
  measured.
- Ran the first hard filter check (does the age posterior tighten under realistic
  arrival mix?): it did **not** — that negative result is documented and later
  calibration stages were stopped on purpose.
- At Oliver’s request, still ran the follow-on calibration and toy-scale exact
  checks as diagnostics (not as claiming the first check passed): coverage was
  too high / ranks skewed (filter looks underconfident), while the small-grid
  exact match stayed within tolerance.
- Set up the project so we can write Python simulations and analyses with a
  clear package layout, automated checks, and a place for team decisions and
  ticket status.

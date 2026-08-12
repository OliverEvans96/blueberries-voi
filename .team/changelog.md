# Changelog

Plain-English notes of what shipped, for non-technical readers.

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

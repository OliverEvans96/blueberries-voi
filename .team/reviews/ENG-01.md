# ENG-01 — Definition of done (Slice 3 / board close-out)

STATUS: APPROVED  
DATE: 2026-08-12  
Covers Slice-3 implement tips **T-054–T-057** (close-out **T-058**); Wave-0
**T-053** recorded DONE in `.team/qa/T-053.md`.

ENG-01 dual-runtime is **complete pending human merge** to `main`. Agents did
**not** merge to `main`; landing on the parent branch is a human decision.

## Definition of done checklist

- [x] Slice-3 QA / verify green for **T-053–T-057** (primary PASS and/or
      `T-XXX-verify.md` PASS; reviews APPROVED for T-054–T-057).
- [x] Client-voice changelog: readers can interact with the live simulator in the
      browser under demo budgets; developers can iterate via the local API.
- [x] Plan `.team/plans/ENG-01-dual-runtime.md` marks ENG-01 slices complete.
- [x] Backlog ENG-01 Done / pending human merge (not Next / Active / parked).
- [x] agent-dev-team: AC pass · reviews APPROVED · qa green · plain-English changelog.

## Non-goals (binding — asserted)

- [x] **Not** a full WASM A rewrite (Option A out of scope).
- [x] **Not** JS-only physics / Option B as the production engine.
- [x] **No** matplotlib / pyarrow in the browser path.
- [x] **No** production-N-in-tab claim (no production-N / N=2000 ResearchParticleFilter + full
      rollout in-tab without dialed demo budgets).
- [x] Honesty / cadence ⚑ cards (VOI-02 / X-06) still out.

## Non-claims

ENG-01 does **not** claim a full WASM rewrite, JS-only production physics,
matplotlib/pyarrow in the browser, production particle counts running unconstrained
in-tab, or honesty/cadence misspecification arms. Site production deploy of the
web mockup remains a human / separate release decision.

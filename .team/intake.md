# Intake 2026-08-12 — Plan and implement M3

## Request (their words)

> Please plan and implement M3 in a new branch. Proceed autonomously and ask me for clarifications at the end.

## What they want

A complete M3 milestone: the value-of-information sweep over knowledge scenarios and spoilage shape
β, planned under `.team/`, implemented with TDD on a new branch from the current integration tip,
verified locally, with clarifying questions deferred to the end rather than blocking progress.

## In scope

- Discover M3 from board ADRs / plans (VOI-01–04, SIM outer loop)
- Plan (ADRs/specs/plan file), implement `voi/` library + smoke gates, changelog / qa / reviews
- Branch from M2 verify tip; do not merge to `main`

## Out of scope

- Honesty / misspecification arms (VOI-02=A ⚑)
- ENG-01 / Pyodide browser packaging
- Cadence or arrival-staggering VOI axes (X-06=A ⚑)
- Merging M2 or M3 onto `main`

## Open questions

Tracked in [GitHub issue #1](https://github.com/OliverEvans96/blueberries-voi/issues/1).

- [ ] Confirm production β grid upper bound and exact 10+ knot placement beyond “includes 1.0”
- [ ] Confirm default `ProfitCosts` for headline VOI vs M2 multi-scenario defaults
- [ ] Whether F1/F1s closed-loop must fully score lot-resolved masks in M3v1 or may smoke-wire

## Assumptions if unanswered

- Production β grid = 10 values from 1.0 to 4.0 inclusive (linspace); CI smoke uses `{1.0, 2.0}`
- Reuse M2 multi-scenario `ProfitCosts(unit_margin=2.0, waste_cost=1.5, stockout_penalty=3.0)`
- Wire all ADR 0096 columns through CRN cell; lot-resolved masks use existing `mask_for` + RBPF

---

# Intake 2026-08-12 — Reopen ENG-01 (browser / dual-runtime simulator)

## Request (their words)

> Okay, excellent - let's reopen ENG-01

## What they want

Unlock the parked browser-simulator track: move past the current “static figures only”
lock so the Python sim/filter stack can run where a reader interacts with it — both
embedded in the browser (Pyodide) and behind an API — with the D3 mockup as the
presentation direction and a thin, efficient Python↔JS boundary (not a full
view-model every tick).

## In scope

- Explicit reopen of ENG-01 (superseding the current static-figures-only lock)
- **Dual runtime:** Pyodide-in-browser (**prod**) and API backend (**dev**), one Python library
- D3 simulator mockup (branch `web/d3-simulator-mockup`) as presentation in Slice 3
- Snapshot / DayDelta; JS owns PnL / economics / ghost / heatmap; flat belief; `step_n`;
  worker-only Pyodide; avoid deep `toJs`
- Packaging for Pyodide embed + API host (derived Abdella; GH Release wheels; CI 3.14)

## Out of scope

- Full WASM rewrite of the filter (option A)
- JS-only physics as the production engine (option B)
- Honesty / misspecification arms, cadence VOI axes, or other ⚑ cards
- Merging M2 / M3 / ENG-01 to `main` (human)

## Open questions

- [x] **Replacement ENG-01 choice:** **A′ dual runtime** — Pyodide worker = **prod** interactive
      path; ASGI API = **dev** host; same library. Not full WASM (A). Not JS-only forward sim as
      production engine (B).
- [x] **API backend now or later:** **Second slice** after common + Pyodide (order: Pyodide first,
      API second, D3 mockup third). API ADR/spec written in Wave 0; implement gated after Slice 1.
- [x] **First `/ticket` slice:** **All** — Wave 0 ADRs/export/packaging/API contracts + plan +
      specs T-042–T-058; then Slice 1 façade/packaging/Pyodide; Slice 2 API; Slice 3 D3.
- [x] **Browser v1 compute scope:** **sim + filter + controller** with dialed budgets (not
      production-N in-tab).
- [x] **Python version target:** **Pyodide 314.0.4 / CPython 3.14.2**; add **3.14** to CI; keep
      **3.11 + 3.12** for native/API until a separate drop decision.
- [x] **Repo boundary:** Python package owns library + packaging + hosts; **D3 mockup is Slice 3**
      in worktree/branch `web/d3-simulator-mockup` (same ticket stream T-053–T-058).
- [x] **Parked packaging prefs still binding?** **Yes** — derived Abdella (no parquet in-browser);
      CI → GitHub Release wheels (not PyPI); no matplotlib in-browser; slim import / browser
      façade; worker-only Pyodide; Snapshot/DayDelta + JS-owned presentation; flat belief;
      `step_n`; avoid deep `toJs`.

## Assumptions if unanswered

*(Superseded by checked answers above — retained for history.)*

- Replacement target = **dual path (A′ + API)**: Pyodide worker for the interactive
  demo; same library callable from an API backend; not a full WASM rewrite (A) and not
  JS-forward-only (B)
- API backend is **in intent** for the reopen but **not** the first implement slice —
  first tickets lock ADR + export contract + packaging/façade for Pyodide; API is a
  named follow-on that must stay compatible
- First `/ticket` after answers = **reopen ADR + thin export contract** (Snapshot /
  DayDelta / belief buffers), then packaging; no D3 site code in the Python-repo tip
- Browser v1 = **sim + filter** live; controller later with budget presets (per prior
  controller handoff notes)
- Keep CI on **3.11 + 3.12** until Pyodide’s supported version forces an explicit bump;
  do not drop 3.11 without a stated reason
- **Repo split:** this repo owns library façade + wheel; Astro/D3 stays in the web
  mockup / site checkout and consumes the release artifact
- Prior packaging prefs remain **binding** unless Oliver revises them in the answers above

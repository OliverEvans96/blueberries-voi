# 0128. Studio UX information architecture — insight strip, decision rail, chapter nav

STATUS: PROPOSED
DATE: 2026-08-15
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: T-124 — T-119 audit remediation + studio UX revamp
TIER: 1
MILESTONE: ENG-01 — interactive studio
RELATED: ADR [0086](./0086-m15-richobs-unobserved-masks.md), [0110](./0110-studio-obs-scenario-ladder.md),
[0123](./0123-lazy-obs-scenario-filter-caches.md), [0125](./0125-studio-show-truth-js-only.md)

## Context

T-119 audits found the studio engine path and single-shell layout are correct, but presentation
lags manager information sets: spoilage on P0, ungated arrival receipt rugs, scenario-blind
controls, redundant belief/P&L plots, and demand sliders that do not preview. Separately, the
observation ladder and run controls are buried in section-specific chrome (Belief chips, Run
panel), making the "what do I know / what can I do" story hard to scan.

ADR 0125 established a global `showTruth` gate for hidden-state geometry. ADR 0086 / 0110 /
0123 established the six-rung knowledge ladder and lazy catch-up. This ADR records how we
**restructure chrome** and **layer scenario availability** without new dependencies, wire changes,
or per-scenario layout forks.

## Decision

We will:

1. **Keep one HTML shell** for all `ScenarioId` values. No alternate `sections.ts` plot lists or
   nav items per rung. Gating uses `scenarioAvailability` (`show` / `dim` / `unavailable`) inside
   fixed slots — complementary to, not replacing, ADR 0125 `showTruth`.
2. **Promote persistent chrome** into three zones:
   - **Insight strip** (header): day index, calendar hint, active scenario title, episode profit.
   - **Store + focus** (main): unchanged column semantics; plots respect availability map.
   - **Decision rail** (sticky aside): Advance/Autopilot/Reset, observation ladder chips, truth
     toggle, consolidated P&L — always visible regardless of active section.
3. **Group sections by user intent** via chapter metadata (`Operate` / `Understand` / `Tune`).
   Section keyboard shortcuts 1–8 stay fixed; chapters are a nav affordance only.
4. **Deduplicate teaching surfaces**: Play owns sales-vs-demand; Belief owns the large heatmap;
   Run panel owns aggregate P&L + sparkline; Pricing exposes full ledger on demand only.
5. **Add comprehension affordances** (glossary drawer, human param labels, day inspector on hover,
   static VOI reference JSON stub, guided path presets) as **JS-only** React components with no
   new npm dependencies.
6. **Staged demand preview** via projector-local `demandSummaryFromConfig` — no engine RPC on
   slider input.

## Alternatives considered

- **Per-scenario layout forks** (hide Arrival section on P0, reorder nav per rung) — rejected;
  T-119 audit PASS on single shell; forks multiply test surface and break keyboard muscle memory.
- **Keep obs chips Belief-only** — rejected; ladder is episode-level state, not a Belief-section
  teaching prop; users miss rung context when exploring Physics or Demand.
- **Collapse store + focus into one column on desktop** — rejected; store timeline is the
  episode spine; merging loses day-by-day rhythm that Play teaches.
- **Fetch live VOI sweep from Python host** — rejected; out of ENG-01 scope; static JSON stub
  with disclaimer until CAL-01 regen lands.

## Consequences

The studio becomes scannable for produce-manager questions ("what day, what rung, what profit,
what can I run") without protocol changes. Cost: `studioLogic.ts` gains gating hooks and inspector
wiring; CSS must support three breakpoints and a sticky rail; implement shards need explicit
`file_owner` on shared files (`sections.ts`, `styles.css`, `studioLogic.ts`, `controls.ts`).
Truth overlay and scenario availability are **two orthogonal gates** — charts must consult both.
Revisit if URL routing or SCN-P2 rung ships (would need new ADR, not incremental IA tweak).

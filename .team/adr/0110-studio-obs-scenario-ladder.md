# 0110. Studio observation scenario is the filter ScenarioId ladder

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: SCN-* / ENG-01 (studio)
MILESTONE: Studio knowledge-scenario wiring (Ticket B)
RELATED: ADR 0086 (RichObs + masks), ADR 0096 (VOI columns), ADR 0022 (SCN-P2 Out)

## Context

The interactive studio still exposes fake observation chips `P0 | P1 | P2` that only change
mock belief blur. The settled M1.5 / M3 knowledge ladder is **`P0 | P1 | F1 | F1s | F2a | F2`**
(`filter.types.ScenarioId`, ADR 0086 masks, ADR 0096 VOI columns). SCN-P2 remains a ⚑ Out card
(ADR 0022) and must not reappear as a studio rung. Meanwhile `EngineSession` /
`day_driver.advance_day` hardcode `P1Obs` from totals only, so even a correct UI chip cannot
change what the filter sees. Episode / multi-scenario paths already emit richest DayLog fields
and apply `mask_for` + `rich_obs_from_day_log`; the interactive path must match that pattern.

Ticket A (belief chart rebin / age-marginal presentation) is a separate slice and must not be
coupled into this wiring decision.

## Decision

We will:

1. Treat studio **`obs_scenario`** as identical to Python **`filter.types.ScenarioId`**:
   `"P0" | "P1" | "F1" | "F1s" | "F2a" | "F2"`. Rename the TypeScript alias from `ObsScenario`
   to `ScenarioId` (same literals). Drop `P2` from types, chips, and mock adapters.
2. Apply `obs_scenario` **only on adapter `init` / `reset` with config** → `EngineSession` →
   `day_driver`. Staging a chip marks the projector config dirty until Reset; mid-episode
   chip clicks do not retarget the live filter mid-stream.
3. Stop hardcoding `P1Obs` in the interactive day driver. Each tick emits the **richest**
   DayLog-shaped fields available from `day_step` (lot maps from `sales_by_cohort` /
   `waste_by_cohort`, receipt meta when a delivery exists — same pattern as
   `sim/episode.py` / `sim/m2_multi_scenario.py`), then builds the filter observation with
   `mask_for(obs_scenario)` + `rich_obs_from_day_log(...)`. The mask chooses visibility;
   the day never invents masked zeros.
4. Default `obs_scenario` is **`P1`**. Snapshot `applied_config` echoes the applied scenario.
5. Keep **SCN-P2 Out** — do not model, mask, or chip it. Do not reopen ADR 0022.
6. Explicit ownership split: **this ADR / Ticket B** owns scenario ladder UI + engine wiring;
   **Ticket A** owns belief chart rebin / age-marginal presentation and must not be required
   to land this decision.

Locked human-facing chip copy (studio):

| Id | Title | Description |
|----|--------|-------------|
| P0 | Books only | Receipts and POS totals only — no daily waste. |
| P1 | Shrink gun | Adds storewide daily waste totals. |
| F1 | Lot ID at POS | Sales broken out by lot. |
| F1s | Lot ID on shrink | Waste broken out by lot. |
| F2a | Pack date on ASN | Narrows the arrival-age prior only. |
| F2 | Age at receipt | Measured age at receipt plus rich lot maps. |

## Alternatives considered

- **Keep P0/P1/P2 blur chips as presentation-only** — rejected because they teach a false
  ladder and never exercise ADR 0086 masks on the live engine path.
- **Apply scenario changes mid-episode without reset** — rejected because particle history
  was conditioned on the prior mask; hot-swapping would silently mix likelihoods.
- **Pass scenario only into the mock blur helper and leave day_driver on P1Obs** — rejected
  because HTTP / Pyodide hosts would still filter as P1 regardless of the chip.
- **Reopen SCN-P2 as a seventh chip** — rejected; ADR 0022 / backlog keep it ⚑ Out.

## Consequences

- **Easy:** Studio, VOI, and Stage A/B share one scenario id vocabulary; interactive demos can
  show real rung differences under shared physics.
- **Hard:** day_driver must carry DayLog-rich fields and a scenario argument; hosts
  (main.ts reset/init, HTTP/Pyodide config merge) must forward `obs_scenario`; mock blur
  helpers must accept the six ids without inventing P2.
- **Locked:** `obs_scenario` ≡ `ScenarioId`; default P1; config applied on reset/init only;
  SCN-P2 stays Out; Ticket A chart work remains a separate ticket.
- **Revisit if:** Oliver reopens SCN-P2 / F3, or the studio gains a mid-episode filter restart
  protocol that is bit-stable under CRN.

# 0125. Studio show-truth is JS-only presentation

STATUS: PROPOSED
DATE: 2026-08-14
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: T-115 — backlog “Frontend truth vs belief audit”
TIER: 1
MILESTONE: ENG-01 — interactive studio

## Context

The studio currently draws sim truth (live lots, receipt-age rugs, lot scatters) on the
same charts as manager beliefs. A produce manager would see books, orders, demand
shape, and filter beliefs — not god-mode lot geometry. ADR [0100](./0100-simulator-export-contract.md)
and [0109](./0109-js-belief-age-count-rebin.md) already send both `belief` and `live_lots`
on Snapshot/DayDelta. Gating truth in the kernel or omitting it on the wire would break
debug overlays and force a second protocol.

Per-day inventory and age-composition charts today sum **truth** lots. Manager mode
needs expected counts/ages from the rolling belief the projector already receives on
each DayDelta.

## Decision

We will:

1. Keep sending `belief` + `live_lots` on the wire. Do **not** add a `showTruth` (or
   equivalent) key to Snapshot/DayDelta. Do not change WASM, Python session, or crates.
2. Default **`showTruth = false`** in the studio. Hidden-state geometry is off until the
   user turns it on.
3. Treat show-truth as **JS presentation**: ViewModel stays complete (still includes
   `live_lots`). Renderers choose what to draw (`truthLots=[]` when off).
4. Persist the toggle in `localStorage` under `blueberries-voi-studio-show-truth`.
   Apply root class `studio--show-truth` when on. Use **one** truth visual language
   (extend existing `.truth-cross` / `.truth-circle`).
5. Mirror rolling **`beliefByDay` / `belief_history`** in the projector from
   `DayDelta.belief` on the same window as `history`, so inventory vs target and age
   composition can use expected bands when the toggle is off.
6. Defer knowledge-scenario-specific chrome (e.g. F2 receipt ages as “observed”) to
   the existing backlog item *Frontend knowledge-scenario UI audit*. V1 gates all
   hidden-state marks with this global toggle only.

## Alternatives considered

- **Omit `live_lots` on the wire when show-truth is off** — rejected because the toggle
  must re-render without an engine RPC, and hosts would need a new Snapshot flag.
- **Default show-truth on (current god-mode)** — rejected; the audit asks that default
  views match a produce manager’s information set.
- **Strip truth from the projector / ViewModel** — rejected; a second incomplete
  ViewModel duplicates mapping and still needs lots in memory for the overlay path.
- **Per-scenario UI forks** — rejected for V1; one layout, one global gate.

## Consequences

Studio charts can show manager books by default and a consistent truth overlay when
asked, without a protocol bump. Cost: JS must keep a rolling belief window and two
inventory/age-comp code paths; chrome numbers that currently use `vm.on_hand` from
truth lots must follow the same selector as charts. Autopilot and policy stay on
belief; they must not start using truth because overlays exist.

# 0038. MOD-16: Lots per delivery below the scanning rung
STATUS: SUPERSEDED BY 0149
DATE: 2026-08-12
BOARD-ID: MOD-16
GROUP: MOD
PROVENANCE: contested
TIER: 1
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: true
SUPERSEDED BY: [0149](./0149-mod-16-three-fixed-lots-per-delivery.md) — Oliver reopened this
card (2026-08-26); option A is replaced by a fixed, known `L = 3` (a structural variant of this
card's option C), not by the option B this card also rejected.

## Context

*Milestone: M2 — A is the M1 setting whichever way this lands.*

**The problem.**

[MOD-01](MOD-01%20Unit%20of%20inventory%20state.md) settled on the **GS1 lot** as the unit of state rather than the receipt cohort. But
**below the lot-scanning rung you cannot know how many lots a delivery contained.** Lot identity is
precisely what [SCN-F1](SCN-F1%20Sunrise%20partial%20%E2%80%94%20lot%20ID%20at%20POS.md) buys. So as things stand, the state has a dimension that is unobservable in
principle at exactly the rungs where the filter does the most work.

This is not a small bookkeeping issue: the number of latent atoms is a structural property of the
state space, and every low-rung filter needs to know it before it can start.

**What is actually true about deliveries.**

- A **case** is certainly one lot — clamshells are filled and coded together at the packhouse.
- A **truckload** from one grower is typically one lot; split across many stores, each store's
  delivery is genuinely single-lot.
- A **DC-picked order** may mix receipts, though for fast-turning berries the DC runs tight FIFO and
  turns in 1–3 days, so mixing is usually mild.
- The failure cases are specific and identifiable: **growing-region transitions** (Chile → Mexico →
  California), **promotional volume** pulled from several receipts at once, and **slow movers**.

Honest position: one to three lots per delivery, usually dominated by one.

**Why C is the interesting one.**

There is a VOI channel hiding here that nothing has counted:

> Lot scanning does not only tell you **which** lot you sold — it tells you **how many lots you
> have**. Below the scanning rung the number of atoms is assumed from the delivery schedule; at it,
> the number is measured.

The "deconvolution with known support" framing that makes this problem tractable quietly assumes the
support is known. Sometimes it isn't, and that is value the ladder has not been charged for.

> **Recommended: C**, with A as the M1 setting so the filter is first validated against a truth it
> can represent exactly.

## Decision

We will adopt **A — Exactly one lot per delivery, always**. Chosen against the card recommendation of **C — Simulator mixes; low-rung filters assume one**.

**A — Exactly one lot per delivery, always.** ⚑ Against the card's recommendation (C). The simulator never mixes. Lot becomes cohort in all but name.

## Alternatives considered

- **B — Simulator mixes; the filter infers how many lots arrived** — not chosen. Correct, and hard: the number of latent atoms becomes a discrete unknown, which turns the filter into a transdimensional inference problem. Well out of proportion to the effect size.
- **C — Simulator mixes; low-rung filters assume one** _(card recommendation; not chosen)_ — not chosen. The resulting error is measured, not hidden.

## Consequences

The simulator never mixes. Lot becomes cohort in all but name.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.
**Oliver reopened this on 2026-08-26; see [0149](./0149-mod-16-three-fixed-lots-per-delivery.md).**

**Depends on:** `MOD-01`, `SCN-F1`

**Milestone:** M2 — controller and multi-scenario

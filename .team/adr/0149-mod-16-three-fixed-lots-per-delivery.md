# 0149. MOD-16 revisit: three fixed lots per delivery, split not multiplied

STATUS: ACCEPTED
DATE: 2026-08-26
BOARD-ID: MOD-16
GROUP: MOD
TIER: 1
SUPERSEDES: [0038](./0038-mod-16-lots-per-delivery-below-the-scanning-rung.md) (option A,
"exactly one lot per delivery, always")
RELATED: [0023](./0023-mod-01-unit-of-inventory-state.md) (MOD-01, unit of inventory state),
[0015](./0015-scn-f1-sunrise-partial-lot-id-at-pos.md) (SCN-F1, lot ID at POS),
[0133](./0133-observation-channel-toggles.md) (orthogonal `code_type` / `delivery_history`
channels), [0130](./0130-f-native-c2-a-unit-pf.md) (f-native unit PF, fixed particle shape),
[0150](./0150-arrival-thermal-break-events.md) (cold-chain break events; each lot draws its
own break-event journey under this ADR's DC model)

## Context

[MOD-16](./0038-mod-16-lots-per-delivery-below-the-scanning-rung.md) chose **A — exactly one
lot per delivery, always** against its own card's recommendation of **C — simulator mixes;
low-rung filters assume one** — and carried "do not reopen without asking Oliver." Oliver
reopened it (`.team/backlog.md`, "Migrate arrival cohorts → proper lots (MOD-16 revisit)").

**Why A made the ladder collapse.** Under A, lot identity is redundant with shelf age: a
M/W/F schedule means every lot on the shelf has a distinct age, and age alone nearly pins the
sales allocation. Measured: books-only 0.109 → pack-date 0.034 → *lot ID +* pack-date 0.032.
GSIN buys almost nothing over F2 because there is nothing for lot identity to distinguish that
age doesn't already distinguish.

**The uncounted channel.** ADR 0038's own card text named a VOI channel nothing has counted:

> Lot scanning does not only tell you *which* lot you sold — it tells you *how many* lots you
> have. Below the scanning rung the number of atoms is assumed from the delivery schedule; at
> it, the number is measured.

Under A the simulator never mixes, so that channel cannot exist even in principle — belief and
truth agree on cardinality everywhere, and there's nothing to learn.

**An intervening investigation, not adopted.** A prior architect report
(`.team/reports/mod-16-filter-options.md`, T-129, report-only, no implementation) explored a
*random* lot count `L ∈ {1, 2, 3}` per delivery, order-quantity-driven, with the filter
injecting one birth cohort per physical lot at every rung ("honest multi-lot," the report's
"Option A"). It recommended that path and rejected the card's original C for production,
reasoning that a low rung which always assumes one lot produces "measured, scenario-dependent
bias on every VOI difference — unacceptable for a project whose headline numbers are small
profit deltas." That report is superseded in substance by this ADR's decision below, which
takes neither the report's recommendation nor the original card's C unmodified — see
Alternatives.

**Hard constraint carried into this revisit:** no meaningful increase in per-day filter
runtime. The T-129 report's own compute analysis flagged that a *random* `k` pressures
`L_DIM` and particle alignment (ADR 0130's fixed `L×U` shape) and multiplies delivery-day
filter cost by `k`. A fixed, known lot count sidesteps both concerns.

## Decision

### 1. `L = 3`, fixed and known, everywhere

The number of lots per delivery is a **constant**, not a per-particle latent (ADR 0038's
option B, transdimensional inference, stays rejected — see Alternatives) and not a random
variable drawn per delivery (the backlog note's framing, and the T-129 report's recommendation,
are both **not** adopted). Every rung — truth, filter, and every observation scenario — knows
`L = 3` as a model constant. What differs by rung is not *whether* three lots exist, but
*whether the filter can tell them apart*.

### 2. Delivery quantity is split, not multiplied

Total units per delivery is unchanged; the case-rounded order quantity is divided across the
three lots. This is what keeps per-day filter runtime flat — the concern the T-129 report
raised against a randomized `k` (each additional lot multiplying the arrival-birth work) does
not apply here, because the total work per delivery (total units aged, scored, evicted) is the
same as under one lot; it's only *segmented* differently under GSIN.

### 3. GSIN holds segments; UPC holds a merged cohort — a structural fork, not a new mask field

A UPC store's inventory record *is* one undifferentiated pile — it cannot track three cohorts
it can't tell apart at the register. So:

- **GSIN:** three segments, each born from its own `ArrivalCondition` (`Duration(d_ℓ)` or
  `Exposure(Λ_ℓ)` — see ADR 0150), each independently scorable for sales and waste.
- **UPC:** one segment of `Q` units, born from the mixture law
  `Law_UPC = (1/L) Σ_ℓ Law(record_ℓ)`.

The UPC store still *receives* all three records (the ASN lists three dates; three loggers came
back) — it just cannot attribute them, so the laws get mixed. **Mix the laws, don't average the
dates:** a mixture of three laws with different means carries the between-lot spread as
variance; averaging dates first would leave only within-lot variance and understate UPC's true
uncertainty.

**No new observation-mask fields.** The three channel switches stay orthogonal:
`delivery_history` controls what journey data arrives (duration only, or the full exposure
trace); `code_type` controls whether that data can be held in per-lot segments at all. The
`waste_by_lot → code_type = Gsin` coupling (`obs.rs`) remains the sole documented exception to
that orthogonality. An earlier draft of this decision proposed a coupled
`delivery_history_by_lot` mask field to let a GSIN store see per-lot journey data while a UPC
store saw only pooled journey data (or vice versa) — **rejected**: the `code_type` /
`delivery_history` fork above already determines whether journey data lands in segments or gets
mixed into one law, so a third field would duplicate information the fork already encodes.

### 4. DC model: independent upstream, shared final leg

```
Λ_ℓ = Λ_upstream,ℓ + Λ_shared
```

Each lot draws its own upstream journey (own duration, own break events — different growers,
regions, pack dates), and one DC→store leg is drawn per delivery and shared across all three.
Traces are spliced: three journeys diverging early, converging onto an identical tail. This is
nearly free because **the filter never conditions on legs** — only on total duration (pack
date) or total exposure (temperature trace, via ADR 0150's `resolve_arrival_exposure`) — so
splitting a journey into legs is a truth-path and trace-rendering change only, made trivial by
exposure additivity. It also fixes the correlation structure honestly: lots on one truck become
correlated (shared final leg) but not identical (independent upstream legs), where option A
made them identical by construction.

### 5. What GSIN now buys, in descending expected effect

1. **Sequential attribution.** Pooled totals cannot distinguish "sales came from the fresh lot,
   leaving a stale shelf" from the reverse. The multinomial allocation term can. Particles
   genuinely differ in allocation (picking weight ∝ `f^σ`); under UPC nothing penalizes that
   diversity, so the posterior spreads further every day.
2. **Composition.** Under GSIN the bag is exactly 13/13/14 units per lot; under UPC it's
   roughly `Multinomial(Q, ⅓, ⅓, ⅓)`, a spread of ~±3 units per lot.
3. **Lot count** — ADR 0038's uncounted third channel, obtained with **no transdimensional
   inference**: the low rung (P0/P1, no lot ID observed) simply assumes one lot per delivery
   while truth always has three, and the resulting error is measured, not hidden. This is
   option C's stated advantage, now honest in a specific sense the original card wasn't: the
   size of the low rung's misspecification is fixed and knowable (it's always "three, believed
   as one"), rather than an unknown random count the low rung would have to guess at.

## Alternatives considered

- **A — Exactly one lot per delivery, always** (ADR 0038, superseded by this ADR) — the
  status quo this ADR replaces. Made lot ID redundant with shelf age and precluded the
  cardinality channel entirely.
- **B — Simulator mixes; the filter infers how many lots arrived** (ADR 0038's option B) —
  stays rejected. Turns the number of latent atoms into a discrete unknown, making the filter a
  transdimensional inference problem; breaks the fixed `L×U` particle-bank shape ADR 0130
  depends on for alignment and catch-up replay. Well out of proportion to the effect size, as
  ADR 0038 already found.
- **Random `L ∈ {1, 2, 3}` per delivery, filter matching truth exactly at every rung**
  (`.team/reports/mod-16-filter-options.md`, T-129 report's recommended "Option A") — considered
  and not adopted. Rejected for three reasons: (a) it requires the low rungs to know the *true*
  cardinality on every delivery to stay unbiased, which erases rather than measures the
  cardinality channel this revisit exists to recover; (b) the report's own compute analysis
  found variable `k` pressures `L_DIM` and particle alignment, and multiplies delivery-day
  arrival cost by `k`; a fixed `L = 3` avoids both; (c) it adds bookkeeping (variable-length
  `lot_offsets` reconciled against a fixed virtual grid) for a distribution the report itself
  says is dominated by one case (`E[k] ≈ 1.1–1.3` under its own PMF sketch) — the honest average
  case looks like A, not like a genuinely uncertain count.
- **Coupled `delivery_history_by_lot` mask field** (an earlier draft of this decision) —
  rejected; subsumed by the `code_type` / `delivery_history` structural fork in §3.
- **Averaging pack dates across lots before mixing, under UPC** — rejected; discards the
  between-lot variance that is exactly what makes the UPC posterior honestly wider than GSIN's.

## Consequences

**Makes easy.** Runtime stays flat: quantity is split, not multiplied, and the DC model is
nearly free because the filter conditions only on totals, never on legs. The cardinality
channel is testable rather than assumed away, since the low rung's misspecification size is
now a fixed, knowable quantity rather than either zero (A) or an unbounded transdimensional
unknown (B).

**Makes hard / costs.** GSIN shelf segment count rises from ~3–5 to ~9–15. Per-lot
Poisson-binomial spoilage DP is `O(n_ℓ · w_ℓ)`, so three smaller lots cost *less* per lot than
one large one at fixed total units — but per-lot loop overhead and the `L×K` belief-wire
payload both roughly triple. Measure, don't assume.

**Locks in.** `L = 3` as a global model constant, not a per-particle latent and not a
per-delivery random draw, until a future ADR reopens it with real-world evidence that lot count
itself carries information worth modeling as uncertain. The `code_type` / `delivery_history`
structural fork (§3) as the sole mechanism connecting observation channels to lot segmentation,
with `waste_by_lot → code_type = Gsin` as the one prior exception, now read as an instance of
the same pattern rather than a one-off.

**Revisit if.** Real delivery data ever motivates modeling lot count as informative or
variable (return to option B territory, now with a concrete effect size to justify the
transdimensional machinery); or GS1 case sizes / DC-picking behavior change enough that "three"
stops being a reasonable fixed stand-in for "one to three, usually dominated by one."

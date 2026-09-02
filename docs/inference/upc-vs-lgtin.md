---
title: UPC vs LGTIN
sources:
  adr: ["0149", "0150"]
  code: [crates/voi_core/src/unit_pf.rs, crates/voi_core/src/unit_ll.rs, crates/voi_core/src/arrival.rs, crates/voi_core/src/obs.rs]
---

# UPC vs LGTIN

A barcode can carry different amounts of detail about the same product. Today, most
stores scan a Universal Product Code (UPC) — a code that says *what* the item is (one
blueberry clamshell) but not which delivery it came from. A newer alternative, LGTIN,
adds a batch or lot number to that same product code: it's a GTIN (Global Trade Item
Number, GS1's standard product identifier) plus a lot number, so it identifies not just
the product but *which production batch* — one specific truckload of blueberries, as
opposed to the next truckload of the identical product. That's a different thing from a
shipment identifier; LGTIN identifies a batch of one product, not a logistics shipment.

This distinction isn't hypothetical. It's the same idea behind Sunrise 2027, a real
grocery-industry push led by GS1 to bring 2D barcodes — capable of carrying a lot number,
a pack date, or even logged temperature history — to checkout alongside today's UPC.
UPC isn't going away; LGTIN is a capability a store can opt into. This page asks: given
that a store could scan either code, how much does that extra detail actually buy the
filter that tracks shelf freshness? It's not two different models bolted together — it's
the same [one-day update](/inference/one-filter-day) run at two different resolutions of
the same evidence, with a structural fork at birth and at scoring.

## The idea

Imagine two clerks recording the same day at the same store. A delivery of 40 units just
arrived as three lots — say 13, 13, and 14 units, each with its own pack date and maybe
its own temperature history. Clerk UPC writes down "40 units in" and, for the day's
activity, "14 sold, 2 wasted" — one pooled number for the whole shop. Clerk LGTIN writes
down "lot #41: 5 sold, 1 wasted; lot #42: 6 sold, 0 wasted; lot #43: 3 sold, 1 wasted" —
the same store totals, broken out by which lot each unit belonged to.

Everything Clerk LGTIN wrote down still adds up to Clerk UPC's numbers. LGTIN hasn't
observed anything *extra* in the sense of a new physical quantity — it's observed the
*same* quantity at finer resolution. That's the core idea: **LGTIN refines UPC's
evidence, it doesn't replace it.** Every LGTIN term the filter scores is a finer-grained
version of the corresponding UPC term evaluated on the same underlying state, and adding
the LGTIN terms back together recovers the UPC term exactly.

The fork isn't only in daily scoring — it starts at birth. Every physical delivery
carries three lots, fixed and known everywhere: in the simulator's truth, in the filter,
and across every scenario on the [observation ladder](/ladder/observation-scenarios). The
delivery's total quantity is *split* across those three lots rather than multiplied, so
per-day filter runtime stays the same regardless of which code a scenario uses — only
LGTIN can tell the lots apart once they hit the register. A UPC store's inventory record
*is* one undifferentiated pile — it has no way to hold three cohorts it can't tell apart.
So under LGTIN the filter creates three separate segments, one per lot, each one seeded
from that lot's own journey data (either how long it spent in transit or how much heat
exposure it accumulated along the way). Under UPC it creates one merged cohort instead,
using a law that blends the three lots' distributions together:

$$
\text{Law}_\text{UPC} = \frac{1}{L}\sum_{\ell=1}^{L} \text{Law}(\text{record}_\ell).
$$

The UPC store still *receives* all three delivery records — three pack dates on the
Advance Ship Notice (ASN), three loggers came back — it just can't attribute them to
specific lots once they're on the shelf. So the three lots' distributions get **mixed,
not averaged**: mixing preserves the spread between lots as variance, while averaging the
dates first would throw that spread away.

Beyond refining pooled totals, LGTIN buys three things a pooled code structurally can't
express, in descending order of expected effect:

1. **Sequential attribution.** A pooled total can't tell "sales came from the fresh lot,
   leaving a stale shelf behind" apart from the reverse story. LGTIN's per-lot allocation
   can.
2. **Composition.** Under LGTIN the shelf holds exactly 13/13/14 units per lot; under UPC
   it's only known up to a roughly even three-way split with a spread of a few units
   either way — a lot-count discrepancy that nothing in a pooled code can penalize.
3. **Lot count itself.** The books-only scenario has no way to represent more than one
   lot per delivery, so it implicitly assumes there's just one — even though the truth is
   always three. Because the model tracks this explicitly, that mismatch is something the
   filter measures rather than something invisible to it.

## The math

For each of the four daily stages, UPC and LGTIN score the same underlying quantity at
different resolutions. ("Poisson-binomial" below just means a calculation that accounts
for every unit's own, slightly different chance of having spoiled.)

| Stage | UPC (pooled) | LGTIN (per lot) |
| --- | --- | --- |
| Spoilage scoring | one Poisson-binomial term against $\text{waste}_\text{tot}$ | one Poisson-binomial term **per lot** $\ell$ against $\text{waste}_\ell$ |
| Sales feasibility | $\mathbb{1}\{\text{alive} \ge \text{sales}_\text{tot}\}$ | $\prod_\ell \mathbb{1}\{\text{alive}_\ell \ge \text{sales}_\ell\}$ |
| Cross-lot allocation | *(none — structurally unobservable)* | $\text{Multinomial}(\text{sales}_1,\dots,\text{sales}_L;\ \text{sales}_\text{tot},\ \text{share}_1,\dots,\text{share}_L)$ |
| Sales removal (unscored) | one pooled without-replacement (WOR) draw | one without-replacement draw **per lot**, conditioned on that lot's count |

LGTIN can never be *less* informative than UPC, and here's why: adding up the per-lot
spoilage terms exactly reproduces the pooled term,

$$
\sum_{\ell} \log P_{\text{PB}}(\text{waste}_\ell \mid \{p_i\}_{i \in \ell}) \;=\; \log P_{\text{PB}}(\text{waste}_\text{tot} \mid \{p_i\}_{i=1}^n)
$$

as long as the per-lot counts sum to the pooled total — because it's the same underlying
population of units either way, just partitioned differently for scoring. The same logic
holds for the feasibility check: passing every per-lot check implies passing the pooled
check. So LGTIN's terms are always a refinement of UPC's, never a departure from them —
with one exception. Cross-lot allocation has no UPC counterpart to refine, because UPC's
sales total says nothing about *how* it split across lots. That row is the genuinely new
information LGTIN alone supplies.

**Lot matching is by identity, not position.** An LGTIN observation names lots by ID,
and those IDs are matched against whichever lots the particle filter still holds — not
by counting "1st segment, 2nd segment." If an observation reports a nonzero count for a
lot the filter has already retired, that day's scoring for that lot quietly falls back to
pooled, UPC-style scoring instead of assigning every particle zero probability and
collapsing the filter.

## Why it's modelled this way

**Lot count is fixed at three, and the total is split, not multiplied.** Lot count is a
constant, not something each particle has to guess or something that varies delivery to
delivery. That keeps the particle filter's memory footprint and per-day runtime the same
across every scenario, while still letting the books-only scenario's blind spot — it
assumes one lot when the truth is always three — show up as a measurable error rather
than being designed away.

**Mix the laws, don't average the dates first.** Which code type and delivery-history
feed a scenario uses already decides whether a lot's journey data lands in its own
segment or gets blended into one shared birth law — no separate switch is needed. Because
the UPC store receives every lot's record but can't attribute it, it uses a pointwise
average of each lot's cumulative distribution function (CDF) — mixing the laws rather
than averaging the dates — which is what preserves the spread between lots as variance
instead of discarding it.

Matching by lot identity rather than position is what makes "refinement, not a different
model" true in practice: a particle's third segment and the simulator's third segment
only refer to the same delivery if both sides agree on what that delivery *is*, and
delivery identity is exactly what LGTIN's code provides that a pooled UPC code can't.
Falling back to pooled scoring on an unmatched lot, rather than killing every particle,
keeps LGTIN's worst case no worse than UPC's — one misaligned observation shouldn't be
able to zero out the entire filter when the same information would have scored fine as a
pooled total.

LGTIN's per-lot terms are scored with exact, closed-form calculations rather than
by drawing random samples and averaging. That choice matters: scoring by random sampling
would make LGTIN's *estimated* variance grow with the number of lots, so on paper LGTIN
could look *less* informative than UPC even though it strictly observes more. That would
be an artifact of how the estimate is computed, not a real property of the evidence.
Scoring exactly is what makes the refinement argument above hold in the actual
implementation, not just as a statement about the underlying math.

**Caveat:** "LGTIN is never less informative than UPC" is a statement about the
likelihood terms with the state held fixed — a non-regression guard checked against
comparable metrics in this project's diagnostics. It is not a proof that LGTIN's belief
strictly beats UPC's on every metric in every run. Finite numbers of particles,
resampling randomness, and the lot-identity fallback above all mean the guarantee is
about what the evidence *could* tell the filter, not a hard bound on what any single run
measures.

## In the code

| Concept | Symbol | Location |
| --- | --- | --- |
| Channel-conditional stage table (module doc) | — | `crates/voi_core/src/unit_pf.rs:1` (module doc) |
| UPC pooled spoilage term | $\log P(W = w_\text{tot})$ | `crates/voi_core/src/unit_ll.rs:82` ([`pb_loglik_pooled`](/api/rust/voi_core/unit_ll/fn.pb_loglik_pooled.html)) |
| LGTIN per-lot spoilage term | $\sum_\ell \log P(W_\ell = w_\ell)$ | `crates/voi_core/src/unit_ll.rs:57` ([`pb_loglik_by_lot`](/api/rust/voi_core/unit_ll/fn.pb_loglik_by_lot.html)) |
| LGTIN feasibility + multinomial allocation | $\mathcal{L}_\text{sales}$ | `crates/voi_core/src/unit_ll.rs:300` ([`loglik_sales_by_units`](/api/rust/voi_core/unit_ll/fn.loglik_sales_by_units.html)) |
| UPC pooled feasibility gate (scoring only) | — | `crates/voi_core/src/unit_pf.rs:429` (`score_sales_evidence`, aggregate branch) |
| UPC pooled removal (unconditional bookkeeping) | — | `crates/voi_core/src/unit_pf.rs:454` (`apply_sales_removal`, aggregate branch) |
| Per-lot picking share (allocation weights) | $\text{share}_\ell$ | `crates/voi_core/src/unit_ll.rs:210` ([`lot_shares_from_freshness`](/api/rust/voi_core/unit_ll/fn.lot_shares_from_freshness.html)) |
| Lot-id → bank-segment matching | — | `crates/voi_core/src/unit_pf.rs:262` ([`project_lot_map`](/api/rust/voi_core/unit_pf/fn.project_lot_map.html)) |
| Unmatched-lot fallback to aggregate scoring | — | `crates/voi_core/src/unit_pf.rs:288` (drop → `None` inside `project_lot_map`, consumed by `DayEvidence::resolve` at `unit_pf.rs:383`) |
| Bank's observed lot segmentation | `lot_offsets` / `lot_ids` | `crates/voi_core/src/unit_pf.rs:53` (`UnitParticleBank` fields) |
| UPC mixture birth law | $\text{Law}_\text{UPC} = \frac{1}{L}\sum_\ell \text{Law}_\ell$ | `crates/voi_core/src/arrival.rs:2098` ([`mixture_law`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.mixture_law)) |
| UPC mixture birth draws | — | `crates/voi_core/src/arrival.rs:2149` ([`sample_filter_birth_units_mixture`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.sample_filter_birth_units_mixture)) |
| LGTIN per-lot birth draws | — | `crates/voi_core/src/arrival.rs:2069` ([`sample_filter_birth_units`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.sample_filter_birth_units)) |
| `code_type` toggles per-lot vs pooled segmentation | `ObsChannels` | `crates/voi_core/src/obs.rs:32` |

## Caveats

This page describes the *scoring and birth* difference between the two channels — it
doesn't say how realistic either channel is for a given store to actually run today (see
the [observation ladder](/ladder/observation-scenarios) pages for that). The refinement
argument also assumes the observed per-lot counts are internally consistent — that they
sum to the observed pooled total. The code doesn't separately reconcile an LGTIN feed
against an independently reported UPC feed if a real deployment somehow supplied both and
they disagreed. And the unmatched-lot fallback means an LGTIN feed with persistently
stale or missing lot IDs quietly behaves like UPC instead of raising an error — the right
failure mode for keeping the filter stable, but one that could mask a wiring bug in the
observation feed if nobody is watching for it.

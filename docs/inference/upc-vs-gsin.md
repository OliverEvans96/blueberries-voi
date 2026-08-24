---
title: UPC vs GSIN
sources:
  code: [crates/voi_core/src/unit_pf.rs, crates/voi_core/src/unit_ll.rs]
---

# UPC vs GSIN

A store can scan inventory two ways: a pooled UPC code that only says "one blueberry
clamshell," or a per-lot GSIN code that also says *which delivery* that clamshell came
from. This page explains what that difference buys the filter — it is not two
different models bolted together, it is the same [one-day update](/inference/one-filter-day)
run at two different resolutions of the same evidence.

![Filter accuracy across UPC-only, lot-resolved, and combined observation setups](/figures/upc-vs-gsin-channel-combos.png)

## The idea

Imagine two clerks recording the same day at the same store. Clerk UPC writes down
"14 units sold, 2 wasted" — one number for the whole shop. Clerk GSIN writes down "lot
#41: 9 sold, 1 wasted; lot #42: 5 sold, 1 wasted" — the same totals, just broken out by
which delivery each unit belonged to.

Everything Clerk GSIN wrote down still adds up to Clerk UPC's numbers — GSIN hasn't
observed anything *extra* in the sense of a new physical quantity, it has just observed
the *same* quantity at finer resolution. That's the core idea: **GSIN refines UPC's
evidence, it doesn't replace it.** Every GSIN term the filter scores is a finer-grained
version of the corresponding UPC term evaluated on the same underlying state, and
summing the GSIN terms back up recovers the UPC term exactly.

The one genuinely new thing GSIN brings is something UPC has no way to express at all:
*which lot* a given sale came from. That breaks an assumption UPC is stuck with — that
sales are exchangeable across lots — and lets the filter score how demand actually split
between an older and a newer delivery, not just how much demand there was in total.

## The math

For each of the four stages, UPC and GSIN score the same underlying quantity at
different resolutions:

| Stage | UPC (pooled) | GSIN (per lot) |
| --- | --- | --- |
| Spoilage scoring | one Poisson-binomial term against $\text{waste}_\text{tot}$ | one Poisson-binomial term **per lot** $\ell$ against $\text{waste}_\ell$ |
| Sales feasibility | $\mathbb{1}\{\text{alive} \ge \text{sales}_\text{tot}\}$ | $\prod_\ell \mathbb{1}\{\text{alive}_\ell \ge \text{sales}_\ell\}$ |
| Cross-lot allocation | *(none — structurally unobservable)* | $\text{Multinomial}(\text{sales}_1,\dots,\text{sales}_L;\ \text{sales}_\text{tot},\ \text{share}_1,\dots,\text{share}_L)$ |
| Sales removal (unscored) | one pooled without-replacement draw | one without-replacement draw **per lot**, conditioned on that lot's count |

Why GSIN can never be *less* informative than UPC: let $f$ be a particle's full
freshness state. The GSIN spoilage term factors the pooled Poisson-binomial PMF along
lot boundaries,

$$
\sum_{\ell} \log P_{\text{PB}}(\text{waste}_\ell \mid \{p_i\}_{i \in \ell}) \;=\; \log P_{\text{PB}}(\text{waste}_\text{tot} \mid \{p_i\}_{i=1}^n)
$$

whenever the per-lot counts sum to the pooled total — the sum of the finer-grained terms
*is* the coarser term, because the underlying Bernoulli trials $\{p_i\}$ are the same
population either way, just partitioned differently for scoring. The same containment
holds for the feasibility gate: passing every per-lot gate implies passing the pooled
gate. So GSIN's per-stage terms are a refinement of UPC's, evaluated on the identical
state — GSIN never discards anything UPC had. The one place the table above shows an
extra row for GSIN with nothing to sum from on the UPC side is cross-lot allocation:
UPC's sales total says nothing about *how* it split across lots, so there is no UPC term
to refine there — that's the new information GSIN alone supplies.

**Lot matching is by identity, not position.** A GSIN observation names lots by id;
those ids are matched against the particle bank's own segment ids (`lot_ids`), not by
counting "1st segment, 2nd segment." If an observation attributes a nonzero count to a
lot id the bank's particles no longer hold — already retired, for instance — that day's
scoring degrades to aggregate, UPC-shaped scoring instead of assigning every particle a
$-\infty$ weight and collapsing the filter.

## Why it's modelled this way

Matching by lot identity, rather than position, is what makes "refinement, not a
different model" true in practice, not just in principle: a particle's third segment and
truth's third segment only refer to the same delivery if both parties agree on what that
delivery *is*, and delivery identity is exactly what GSIN's serialized code provides that
UPC's pooled code doesn't. Falling back to aggregate scoring on an unmatched lot id,
rather than killing every particle, keeps GSIN's worst case no worse than UPC's — a
single misaligned observation shouldn't be able to zero out the entire bank when the
same information would have scored fine as a pooled total.

GSIN's per-lot terms are scored with closed-form Poisson-binomial and multinomial terms
rather than single-sample Monte Carlo draws. Scoring with single samples would make
GSIN's *estimated* variance compound with lot count, so on paper GSIN could look *less*
informative than UPC even though it strictly observes more — an artifact of the
estimator, not a property of the evidence. Making the scoring itself exact and
deterministic is what makes the refinement argument above hold in the implementation,
not just as a statistical statement about the true likelihood.

**Caveat:** "GSIN is never less informative than UPC" is a statement about the
*likelihood terms*, holding the state fixed — it is a non-regression guard checked
against comparable metrics in this codebase's diagnostics, not a proof that GSIN's
*posterior* strictly dominates UPC's on every metric in every run. Finite particle counts,
resampling variance, and the lot-identity fallback above all mean the guarantee is about
what the evidence *could* tell the filter, not a hard bound on what any single run
measures.

## In the code

| Concept | Symbol | Location |
| --- | --- | --- |
| Channel-conditional stage table (doc comment) | — | `crates/voi_core/src/unit_pf.rs:1` (module doc) |
| UPC pooled spoilage term | $\log P(W = w_\text{tot})$ | `crates/voi_core/src/unit_ll.rs:82` ([`pb_loglik_pooled`](/api/rust/voi_core/unit_ll/fn.pb_loglik_pooled.html)) |
| GSIN per-lot spoilage term | $\sum_\ell \log P(W_\ell = w_\ell)$ | `crates/voi_core/src/unit_ll.rs:57` ([`pb_loglik_by_lot`](/api/rust/voi_core/unit_ll/fn.pb_loglik_by_lot.html)) |
| GSIN feasibility + multinomial allocation | $\mathcal{L}_\text{sales}$ | `crates/voi_core/src/unit_ll.rs:321` ([`loglik_sales_by_units`](/api/rust/voi_core/unit_ll/fn.loglik_sales_by_units.html)) |
| UPC pooled feasibility gate + removal | — | `crates/voi_core/src/unit_pf.rs:353` (`score_and_remove_sales`, aggregate branch) |
| Per-lot picking share (the allocation weights) | $\text{share}_\ell$ | `crates/voi_core/src/unit_ll.rs:231` ([`lot_shares_from_freshness`](/api/rust/voi_core/unit_ll/fn.lot_shares_from_freshness.html)) |
| Lot-id → bank-segment matching | — | `crates/voi_core/src/unit_pf.rs:254` ([`project_lot_map`](/api/rust/voi_core/unit_pf/fn.project_lot_map.html)) |
| Unmatched-lot fallback to aggregate scoring | — | `crates/voi_core/src/unit_pf.rs:280` (drop → `None` inside `project_lot_map`, consumed by `DayEvidence::resolve` at `unit_pf.rs:311`) |
| Bank's observed lot segmentation | `lot_offsets` / `lot_ids` | `crates/voi_core/src/unit_pf.rs:54` (`UnitParticleBank` fields) |

## Caveats

This page describes the *scoring* difference between the two channels — it says nothing
about how often either channel is realistic for a given store to actually run (that's
covered by the [observation ladder](/ladder/rungs) pages). The refinement argument also
assumes the observed per-lot counts are internally consistent (they sum to the observed
pooled total); the code does not separately reconcile a GSIN feed against an
independently reported UPC feed if a real deployment somehow supplied both and they
disagreed. And the unmatched-lot fallback means a GSIN feed with persistently stale or
missing lot ids quietly behaves like UPC rather than raising an error, which is the
right failure mode for filter stability but could mask a wiring bug in the observation
feed itself if nobody is watching for it.

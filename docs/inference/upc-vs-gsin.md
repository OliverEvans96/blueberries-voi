---
title: UPC vs GSIN
sources:
  adr: ["0149", "0150"]
  code: [crates/voi_core/src/unit_pf.rs, crates/voi_core/src/unit_ll.rs, crates/voi_core/src/arrival.rs, crates/voi_core/src/obs.rs]
---

# UPC vs GSIN

A store can scan inventory two ways: a pooled UPC code that only says "one blueberry
clamshell," or a per-lot GSIN code that also says *which delivery lot* that clamshell came
from. Every physical delivery carries **three lots** (`L = 3`, fixed and known everywhere —
truth, filter, and every observation scenario). Total case quantity is **split** across those
three lots, not multiplied, so per-day filter runtime stays flat while GSIN can finally tell
lots apart at the register.

This page explains what that difference buys the filter — it is not two different models
bolted together, it is the same [one-day update](/inference/one-filter-day) run at two
different resolutions of the same evidence, with a structural fork at birth and scoring.

## The idea

Imagine two clerks recording the same day at the same store. A delivery of 40 units just
arrived as **three lots** — say 13, 13, and 14 units with different pack dates and (maybe)
different temperature histories. Clerk UPC writes down "40 units in" and, for the day's
activity, "14 sold, 2 wasted" — one pooled number for the whole shop. Clerk GSIN writes
down "lot #41: 5 sold, 1 wasted; lot #42: 6 sold, 0 wasted; lot #43: 3 sold, 1 wasted" —
the same store totals, broken out by which lot each unit belonged to.

Everything Clerk GSIN wrote down still adds up to Clerk UPC's numbers — GSIN hasn't
observed anything *extra* in the sense of a new physical quantity, it has just observed
the *same* quantity at finer resolution. That's the core idea: **GSIN refines UPC's
evidence, it doesn't replace it.** Every GSIN term the filter scores is a finer-grained
version of the corresponding UPC term evaluated on the same underlying state, and
summing the GSIN terms back up recovers the UPC term exactly.

The fork is not only in daily scoring. A UPC store's inventory record *is* one
undifferentiated pile — it cannot hold three cohorts it cannot tell apart at the register.
So under **GSIN** the filter births **three segments**, each from its own
`ArrivalCondition` (`Duration(d_ℓ)` or `Exposure(Λ_ℓ)` per lot). Under **UPC** it births
**one merged cohort** of `Q` units from the mixture law

$$
\text{Law}_\text{UPC} = \frac{1}{L}\sum_{\ell=1}^{L} \text{Law}(\text{record}_\ell).
$$

The UPC store still *receives* all three delivery records (three pack dates on the ASN;
three loggers came back) — it just cannot attribute them, so the laws get **mixed, not
averaged**: mixing preserves between-lot spread as variance; averaging dates first would
discard it.

Beyond refinement of pooled totals, GSIN now buys three things UPC structurally cannot
express, in descending expected effect:

1. **Sequential attribution.** Pooled totals cannot distinguish "sales came from the fresh
   lot, leaving a stale shelf" from the reverse. The multinomial allocation term can.
2. **Composition.** Under GSIN the bag is exactly 13/13/14 units per lot; under UPC it is
   roughly `Multinomial(Q, ⅓, ⅓, ⅓)` — a spread of ~±3 units per lot that nothing in a
   pooled code can penalize.
3. **Lot count** — the cardinality channel ADR 0038 named but never counted: the low rung
   assumes one lot per delivery while truth always has three, and that misspecification is
   measured rather than hidden.

## The math

For each of the four daily stages, UPC and GSIN score the same underlying quantity at
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

**Fixed $L = 3$, split quantity.** Lot count is a model constant, not a per-particle latent
and not a per-delivery random draw — that keeps ADR 0130's fixed `L×U` particle shape and
flat delivery-day cost while still letting the low rung's "believes one lot, truth has
three" error be measured.

**Mix the laws, don't average the dates.** The `code_type` / `delivery_history` fork
already decides whether journey data lands in per-lot segments or gets mixed into one
birth law; no third mask field is needed. UPC receives every lot's record but cannot
attribute, so birth uses `mixture_law` — a pointwise average of component CDFs — rather
than one shared condition.

Matching by lot identity, rather than position, is what makes "refinement, not a
different model" true in practice: a particle's third segment and truth's third segment
only refer to the same delivery if both parties agree on what that delivery *is*, and
delivery identity is exactly what GSIN's serialized code provides that UPC's pooled code
doesn't. Falling back to aggregate scoring on an unmatched lot id, rather than killing
every particle, keeps GSIN's worst case no worse than UPC's — a single misaligned
observation shouldn't be able to zero out the entire bank when the same information would
have scored fine as a pooled total.

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
| Channel-conditional stage table (module doc) | — | `crates/voi_core/src/unit_pf.rs:1` (module doc) |
| UPC pooled spoilage term | $\log P(W = w_\text{tot})$ | `crates/voi_core/src/unit_ll.rs:82` ([`pb_loglik_pooled`](/api/rust/voi_core/unit_ll/fn.pb_loglik_pooled.html)) |
| GSIN per-lot spoilage term | $\sum_\ell \log P(W_\ell = w_\ell)$ | `crates/voi_core/src/unit_ll.rs:57` ([`pb_loglik_by_lot`](/api/rust/voi_core/unit_ll/fn.pb_loglik_by_lot.html)) |
| GSIN feasibility + multinomial allocation | $\mathcal{L}_\text{sales}$ | `crates/voi_core/src/unit_ll.rs:300` ([`loglik_sales_by_units`](/api/rust/voi_core/unit_ll/fn.loglik_sales_by_units.html)) |
| UPC pooled feasibility gate (scoring only) | — | `crates/voi_core/src/unit_pf.rs:429` (`score_sales_evidence`, aggregate branch) |
| UPC pooled removal (unconditional bookkeeping) | — | `crates/voi_core/src/unit_pf.rs:454` (`apply_sales_removal`, aggregate branch) |
| Per-lot picking share (allocation weights) | $\text{share}_\ell$ | `crates/voi_core/src/unit_ll.rs:210` ([`lot_shares_from_freshness`](/api/rust/voi_core/unit_ll/fn.lot_shares_from_freshness.html)) |
| Lot-id → bank-segment matching | — | `crates/voi_core/src/unit_pf.rs:262` ([`project_lot_map`](/api/rust/voi_core/unit_pf/fn.project_lot_map.html)) |
| Unmatched-lot fallback to aggregate scoring | — | `crates/voi_core/src/unit_pf.rs:288` (drop → `None` inside `project_lot_map`, consumed by `DayEvidence::resolve` at `unit_pf.rs:383`) |
| Bank's observed lot segmentation | `lot_offsets` / `lot_ids` | `crates/voi_core/src/unit_pf.rs:53` (`UnitParticleBank` fields) |
| UPC mixture birth law | $\text{Law}_\text{UPC} = \frac{1}{L}\sum_\ell \text{Law}_\ell$ | `crates/voi_core/src/arrival.rs:2098` ([`mixture_law`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.mixture_law)) |
| UPC mixture birth draws | — | `crates/voi_core/src/arrival.rs:2149` ([`sample_filter_birth_units_mixture`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.sample_filter_birth_units_mixture)) |
| GSIN per-lot birth draws | — | `crates/voi_core/src/arrival.rs:2069` ([`sample_filter_birth_units`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.sample_filter_birth_units)) |
| `code_type` toggles per-lot vs pooled segmentation | `ObsChannels` | `crates/voi_core/src/obs.rs:32` |

## Caveats

This page describes the *scoring and birth* difference between the two channels — it says
nothing about how often either channel is realistic for a given store to actually run
(that's covered by the [observation ladder](/ladder/observation-scenarios) pages). The
refinement argument also assumes the observed per-lot counts are internally consistent
(they sum to the observed pooled total); the code does not separately reconcile a GSIN
feed against an independently reported UPC feed if a real deployment somehow supplied both
and they disagreed. And the unmatched-lot fallback means a GSIN feed with persistently
stale or missing lot ids quietly behaves like UPC rather than raising an error, which is
the right failure mode for filter stability but could mask a wiring bug in the observation
feed itself if nobody is watching for it.

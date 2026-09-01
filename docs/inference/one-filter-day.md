---
title: One Filter Day
sources:
  code: [crates/voi_core/src/unit_pf.rs, crates/voi_core/src/unit_ll.rs, crates/voi_core/src/physics.rs]
---

# One Filter Day

Every day, the particle filter turns yesterday's belief plus today's observation into
today's belief. It does this by running the *same* four-stage update — spoilage, sales,
resample, birth — on every particle in the bank, whether the store scans a pooled UPC
code or a per-lot LGTIN code. This page walks through those four stages once, in order,
so the other inference pages can point back at it instead of re-deriving the mechanics.

## The idea

Think of one particle as one complete guess at "here is exactly how fresh every live
unit on the shelf is right now." The filter carries a whole population of these guesses
(a few hundred, typically) and reweights them each day by how well they explain what
was actually observed — some spoilage count, some sales count, maybe nothing at all.

A day breaks into four moves, always in this order:

1. **Spoilage.** Before anything else happens today, some live units die overnight.
   If the store reported a waste count, the filter scores each particle by how
   plausible that count is given the particle's own freshness values, then figures out
   *which* units most plausibly died and ages the survivors just short of dying. If no
   waste was reported, everyone just ages by one unconditional random step.
2. **Sales.** Customers pick units, preferring fresher ones. The filter checks that each
   particle actually has enough live stock to cover the sales, optionally scores how
   sales split across lots (only possible if lots are separately identified), and then
   removes the sold units from the particle's state.
3. **Resample.** Particles that explained the day well get copied more often than
   particles that explained it poorly; particles that are completely inconsistent with
   the day's evidence get dropped.
4. **Birth and retire.** A new delivery arrives as one new lot, and each of its units
   gets a starting freshness drawn from the arrival law appropriate to what this
   observation scenario knows about the shipment (see
   [Birth freshness](/inference/birth-freshness)). Lots that no particle believes still
   hold a live unit are quietly retired from every row.

The one thing to hold onto: **all of the randomness in a filter day lives in guessing
which units died, how much the survivors decayed, and which units got sold** — not in
scoring how likely the day's data was. The importance weight is a deterministic function
of the particle's state and the day's counts. That split matters for what follows.

## The math

Let $f_i \in [0, 1]$ be unit $i$'s freshness just before today's aging step, and let
$n$ be the number of live units ($f_i > 0$) under consideration (the whole store for
UPC, one lot's worth for a LGTIN per-lot term).

**Spoilage — the per-unit death probability.** The store's daily gamma decrement law is
shared across units — same shape $k$ and scale $\theta$ — but every live unit draws its
own decrement $\delta_i$ independently. A unit dies today iff its draw is severe enough
to clear its remaining freshness:

$$
p_i = P(\delta_i \ge f_i) = 1 - F_\Gamma(f_i)
$$

where $F_\Gamma$ is the decrement's CDF. These $p_i$ are independent but *not*
identical — a nearly-spoiled unit ($f_i$ small) has a much higher $p_i$ than a fresh one.

**Spoilage — scoring the observed count.** With $n$ independent, non-identical
Bernoulli trials, the number that "succeed" (die) follows a **Poisson-binomial**
distribution. Its PMF has no closed form but is exact and cheap via a forward DP:

$$
\alpha_0(0) = 1, \qquad
\alpha_i(j) = \alpha_{i-1}(j)\,(1 - p_i) + \alpha_{i-1}(j-1)\,p_i
$$

and $P(W = w) = \alpha_n(w)$. UPC scores one such term against the pooled waste total;
LGTIN scores one term *per lot* against that lot's own waste count.

**Spoilage — the adapted proposal.** Rather than aging every unit blind and hoping the
death count matches, the filter runs the same DP *backward* to sample exactly which
units died, conditioned on the observed count $w$ actually being right — a fully adapted
proposal. Surviving units then draw their decrement from the same gamma law but
*truncated* to $[0, f_i)$, so they land just short of spoiling instead of risking a draw
that would have killed them. Because the proposal already matches the target exactly,
the resulting importance weight reduces to the Poisson-binomial PMF above — nothing
extra to correct for.

**Sales — feasibility and (under LGTIN) allocation.** Let $\text{sales}_\ell$ be the sales
attributed to lot $\ell$, and let $w_i \propto \max(f_i, 0)^\sigma$ be the picking weight
that favors fresher units (or uniform, if the store's picking is set to uniform). Define
each lot's picking share $\text{share}_\ell = \sum_{i \in \ell} w_i \big/ \sum_i w_i$
(pre-removal). LGTIN scores

$$
\mathcal{L}_\text{sales} = \Big[\textstyle\prod_\ell \mathbb{1}\{\text{alive}_\ell \ge \text{sales}_\ell\}\Big] \cdot \text{Multinomial}(\text{sales}_1, \dots, \text{sales}_L;\ \text{sales}_\text{tot},\ \text{share}_1, \dots, \text{share}_L)
$$

UPC has no per-lot identities to split across, so it scores only the pooled feasibility
gate, $\mathbb{1}\{\text{alive} \ge \text{sales}_\text{tot}\}$ — a $0$ or $1$ (in log
space, $-\infty$ or $0$), with no allocation term at all.

**Sales — removal.** Whichever channel is active, the *actual* units removed from the
particle's state are chosen by a sequential without-replacement draw using that same
picking-weight kernel — one draw at a time, weight renormalized over what's left. This
draw is never scored into the importance weight; it only mutates state, mirroring how
truth itself removes units.

**Resample.** Weights combine additively in log space, $\log w_i \mathrel{+}= \log\mathcal{L}_\text{spoilage} + \log\mathcal{L}_\text{sales}$,
then get max-subtracted before exponentiating for numerical stability. A systematic
resample draws new parent indices from the normalized weights and copies each parent's
*entire* freshness row — never a partial edit of one unit — into the child particle.

## Why it's modelled this way

Every unit within a lot ages and spoils independently — each live unit draws its own
daily decrement from the shared gamma law, rather than the whole store or lot sharing a
single decrement. That's what lets units within a lot diverge in freshness before any of
them spoil, which is what makes a per-lot waste count carry information a pooled count
doesn't: if a lot's units were freshness-homogeneous by construction, a per-lot waste
count could only reject particles whose lots were ordered wrong, not sharpen the
posterior on freshness *level*.

The fully adapted death proposal follows a standing design principle in this codebase:
importance weights should be exact and deterministic given the day's evidence, not a
Monte Carlo estimate re-scored into the weight. Scoring sales as "sample one
weighted-without-replacement path, then score that path's probability" would conflate
sampling with scoring, and would make LGTIN — despite observing *more* — pay a variance
penalty for every extra lot it scored separately, making its posteriors *more* diffuse
than UPC's on the same data. Splitting the sales likelihood into a deterministic
closed-form term (the multinomial allocation above) and a separate, unscored
state-transition removal avoids that.

**Caveat:** the Poisson-binomial DP costs $O(n \cdot w)$ per lot segment per particle per
day. That's affordable at the particle and unit counts this project runs at, and it
scales with both the day's death count and the segment size.

## In the code

| Concept | Symbol | Location |
| --- | --- | --- |
| Per-unit spoil probability | $p_i = P(\delta \ge f_i)$ | `crates/voi_core/src/physics.rs:356` ([`GammaDecrementTable::spoil_prob`](/api/rust/voi_core/physics/struct.GammaDecrementTable.html#method.spoil_prob)) |
| Live-unit spoil-probability vector | $p_1,\dots,p_n$ | `crates/voi_core/src/unit_ll.rs:14` ([`spoil_probs_from_freshness`](/api/rust/voi_core/unit_ll/fn.spoil_probs_from_freshness.html)) |
| Poisson-binomial log-PMF (DP) | $\log P(W=w)$ | `crates/voi_core/src/unit_ll.rs:27` ([`pb_log_pmf`](/api/rust/voi_core/unit_ll/fn.pb_log_pmf.html)) |
| LGTIN per-lot spoilage likelihood | $\sum_\ell \log P(W_\ell = w_\ell)$ | `crates/voi_core/src/unit_ll.rs:57` ([`pb_loglik_by_lot`](/api/rust/voi_core/unit_ll/fn.pb_loglik_by_lot.html)) |
| UPC pooled spoilage likelihood | $\log P(W = w_\text{tot})$ | `crates/voi_core/src/unit_ll.rs:82` ([`pb_loglik_pooled`](/api/rust/voi_core/unit_ll/fn.pb_loglik_pooled.html)) |
| Backward death-set proposal (pooled) | $q(\text{deaths} \mid f, w)$ | `crates/voi_core/src/unit_ll.rs:88` ([`pb_sample_deaths`](/api/rust/voi_core/unit_ll/fn.pb_sample_deaths.html)) |
| Backward death-set proposal (per lot) | — | `crates/voi_core/src/unit_ll.rs:158` ([`pb_sample_deaths_by_lot`](/api/rust/voi_core/unit_ll/fn.pb_sample_deaths_by_lot.html)) |
| Truncated survivor decrement | $\delta_i \mid \delta_i < f_i$ | `crates/voi_core/src/physics.rs:209` ([`draw_gamma_decrement_truncated`](/api/rust/voi_core/physics/fn.draw_gamma_decrement_truncated.html)) |
| Apply deaths + truncated survivor aging | — | `crates/voi_core/src/unit_ll.rs:189` ([`apply_pb_aging_proposal`](/api/rust/voi_core/unit_ll/fn.apply_pb_aging_proposal.html)) |
| Unconditional aging (no waste observed) | — | `crates/voi_core/src/physics.rs:252` ([`apply_gamma_aging_independent`](/api/rust/voi_core/physics/fn.apply_gamma_aging_independent.html)) |
| Picking weight | $w_i \propto \max(f_i,0)^\sigma$ | `crates/voi_core/src/physics.rs:380` ([`picking_weights_f`](/api/rust/voi_core/physics/fn.picking_weights_f.html)) |
| Per-lot picking share | $\text{share}_\ell$ | `crates/voi_core/src/unit_ll.rs:210` ([`lot_shares_from_freshness`](/api/rust/voi_core/unit_ll/fn.lot_shares_from_freshness.html)) |
| Cross-lot multinomial term | $\text{Multinomial}(\cdot)$ | `crates/voi_core/src/unit_ll.rs:231` ([`multinomial_log_pmf`](/api/rust/voi_core/unit_ll/fn.multinomial_log_pmf.html)) |
| LGTIN sales feasibility + allocation | $\mathcal{L}_\text{sales}$ | `crates/voi_core/src/unit_ll.rs:300` ([`loglik_sales_by_units`](/api/rust/voi_core/unit_ll/fn.loglik_sales_by_units.html)) |
| UPC sales feasibility (scoring only) | — | `crates/voi_core/src/unit_pf.rs:429` (`score_sales_evidence`) |
| Unscored sales removal (unconditional bookkeeping) | — | `crates/voi_core/src/unit_pf.rs:454` (`apply_sales_removal`) |
| Unscored WOR removal draw | — | `crates/voi_core/src/unit_ll.rs:260` ([`sequential_kernel_path_logprob`](/api/rust/voi_core/unit_ll/fn.sequential_kernel_path_logprob.html)) |
| Birth: append one lot segment | — | `crates/voi_core/src/unit_pf.rs:119` (`push_lot_births`), called from the birth block at `unit_pf.rs:707` |
| Systematic resample | — | `crates/voi_core/src/unit_pf.rs:229` ([`systematic_resample`](/api/rust/voi_core/unit_pf/fn.systematic_resample.html)) |
| Retire dead-in-every-particle lots | — | `crates/voi_core/src/unit_pf.rs:134` (`prune_dead_prefix`) |
| Full day orchestration | — | `crates/voi_core/src/unit_pf.rs:577` ([`filter_step_unit_with_birth_cached`](/api/rust/voi_core/unit_pf/fn.filter_step_unit_with_birth_cached.html)) |

## Caveats

The Poisson-binomial model assumes each live unit's death today is independent of every
other unit's, conditional on its own freshness — there is no shared "bad batch" shock
beyond what the common gamma shape and scale already imply. The filter never observes
any individual unit's freshness directly; it only ever sees aggregate counts (how many
died, how many sold, optionally split by lot), so correction is coarse — a particle
either survives resampling wholesale or it doesn't. There is no mechanism by which a
day's evidence reaches in and adjusts one surviving unit's freshness value directly; it
only ever reweights *which whole-store hypothesis* to keep. And because the death set and
the sales removal are themselves random draws (not the true underlying identities), two
particles that agree on every observable count can still disagree about exactly *which*
physical units were sold or spoiled — that's an irreducible identifiability gap the
per-unit grid does not resolve.

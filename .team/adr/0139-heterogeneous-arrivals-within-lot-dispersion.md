# 0139. Within-lot aleatoric birth dispersion on truth and filter

STATUS: PROPOSED
DATE: 2026-08-21
TICKET: T-138
RELATED: [0130](./0130-f-native-c2-a-unit-pf.md) (f-native C2-A unit PF),
[0133](./0133-observation-channel-toggles.md) (orthogonal observation channels),
[0137](./0137-observed-lot-segmentation-and-exact-spoilage-likelihood.md) (shared-decrement
spoilage, LGTIN homogeneity theorem),
[0138](./0138-arrival-f-birth-wiring.md) (single lot-mean birth draw wired through session/VOI;
**distinct ticket** — does not introduce within-lot spread)

## Context

ADR 0137 unified spoilage scoring on the shared gamma decrement and documented a structural
limit of the **lot-uniform birth** model: every live unit in a delivery segment carries the
same freshness, so a lot spoils all-or-nothing and the store's order statistics are just the
lot values. Under that homogeneity, measured over random cohort-consistent shelves
(`lgtin_waste_never_narrows_the_pooled_interval`), the LGTIN per-lot spoilage interval
`I_lgtin` was **exactly** the pooled interval in ~91% of draws and **empty** otherwise — a
strictly tighter non-empty interval **never** occurred. `waste_by` therefore falsifies
mis-ordered particles but cannot sharpen the posterior over the shared decrement.

Physical receipts are not lot-uniform: clamshells within a GS1 lot differ in transit
exposure and pack timing. The simulator and filter still extend deliveries with
`vec![birth_f; U]`, and rollout forward simulation initializes belief units by repeating the
lot marginal mean `e_f` — collapsing within-lot uncertainty that the filter posterior may
carry. That mismatch blocks LGTIN from exploiting spoilage as a **level** channel and biases
rollout paths.

ADR 0138 wired the **lot-mean** birth freshness from receipt metadata through session, VOI,
and F2 filter birth. It did **not** add aleatoric within-lot spread or a dedicated birth CRN
stream. `f2a_transit_uncertainty_sd` remains an **epistemic** channel knob (pack-date transit
width on τ-days before `age_to_f`); it must not be overloaded as a within-lot aleatoric
parameter.

## Decision

**Stage A (T-138)** introduces **within-lot aleatoric dispersion** on both ground truth and
filter birth, without changing the shared-decrement likelihood machinery from ADR 0137:

1. **`ModelParams.arrival_dispersion_sd`** — a new scalar, independent of
   `f2a_transit_uncertainty_sd`, controlling aleatoric spread of per-unit birth freshness
   around the lot mean. Default **0.0** preserves legacy lot-uniform behaviour.

2. **Truth birth** — `shipments::birth_f_units` draws one freshness value per delivered unit
   from the lot mean (existing epistemic paths: F2 Dirac, F2a Gaussian, shipment mix) plus
   aleatoric noise scaled by `arrival_dispersion_sd`. `unit_day_step` extends segments with
   this vector instead of a uniform fill.

3. **Filter birth** — after the existing lot-mean draw per particle (`birth_f`), spread units
   independently per particle using the same aleatoric law; `push_lot` already accepts
   per-particle birth vectors.

4. **`STREAM_BIRTH` CRN** — a dedicated semantic stream (`:birth`) for within-lot dispersion
   draws in session, VOI, rollout, `alpha_tune`, and Python `rng.py`, independent of
   `:arrival_ship` / `:arrival_sensor` used for epistemic lot-mean selection.

5. **Rollout belief init** — `unit_state_from_f_belief` samples per-unit freshness from each
   lot's marginal over `f_grid` (stochastic init under CRN), not `repeat_n(e_f, n)`.

6. **Likelihood unchanged** — `delta_interval_loglik`, `spoil_delta_interval`, and
   `spoil_delta_interval_by_lot` stay on the ADR 0137 shared-decrement path; no return to
   binomial waste.

7. **Acceptance test supersession** — replace
   `lgtin_waste_never_narrows_the_pooled_interval` with a converse that shows strictly tighter
   non-empty `I_lgtin ⊂ I_pooled` can occur when `arrival_dispersion_sd > 0`, and that
   `arrival_dispersion_sd = 0` recovers the ADR 0137 homogeneity limit.

Epistemic channel draws (shipment index, pack-date Gaussian width, F2 Dirac age) are
**unchanged in mechanism**; only the aleatoric within-lot layer is new.

## Alternatives considered

- **Change the spoilage likelihood first (Stage B)** — rejected for this ticket. Tightening
  `I_lgtin` requires heterogeneous unit freshness inside segments; without Stage A births the
  interval algebra has nothing to intersect. Stage B (T-139) may revisit contrast-sensitive
  weighting once dispersion exists.

- **Reuse `f2a_transit_uncertainty_sd` for within-lot spread** — rejected. That parameter is
  tied to the F2a pack-date **observation channel** (ADR 0133); conflating epistemic transit
  uncertainty with aleatoric pack-to-pack variation breaks scenario orthogonality and studio
  dim/show rules for `f2a_transit_sd`.

- **Filter lot-uniform, truth dispersed** — rejected. Structural mismatch reintroduces the
  phantom-mass and interval-emptying pathologies ADR 0137 fixed; LGTIN diagnostics would score
  a generative model the filter does not represent.

- **Deterministic within-lot quantiles from marginals (no new stream)** — rejected. Rollout
  and truth/filter CRN pairing require an explicit `:birth` stream so dispersion draws do not
  advance epistemic streams or collide across code paths.

## Consequences

- **LGTIN spoilage can sharpen the decrement posterior** when units within a lot disagree on
  freshness — the converse test is the observable proof. This is the intended unlock for
  measured LGTIN level gains beyond lot-attribution alone.
- **ESS may drop** when dispersion increases particle diversity within segments; resample cost
  is unchanged but weight degeneracy may rise — monitor `StepDiagnostics.ess` in
  `lgtin_upc_diag`.
- **`count_bias` must stay near zero** under zero-init + observed arrivals (ADR 0136/0137
  conservation contract); dispersion must not inflate row length or alive mass.
- **Stage B (T-139)** may adjust cross-lot sales allocation or contrast weighting once
  heterogeneous births are baseline.
- **Stage C (T-140)** may extend to multi-lot-per-delivery (MOD-16 option A) on top of
  within-lot dispersion.
- **Default `arrival_dispersion_sd = 0`** keeps existing episodes bit-identical aside from
  rollout init sampling (rollout fix is a separate behavioural change even at sd=0).
- **Runtime:** one extra RNG vector per delivery on truth and filter; order unchanged vs
  `N=200` particle bank.

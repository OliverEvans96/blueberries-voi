# 0110. MOD-09 reopen: known NB with calendar DOW×week structure

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: MOD-09
GROUP: MOD
PROVENANCE: CAL-01 Wave 0 — Oliver reopen of i.i.d. demand
TIER: 1
MILESTONE: CAL-01 — calendar realism
SUPERSEDES: 0031

## Context

ADR [0031](./0031-mod-09-demand-model.md) locked **negative binomial, i.i.d., distribution known to
every policy**. The “known to every policy” thesis remains correct: forecasting ≠ ordering; policies
differ only in age knowledge.

Oliver reopened MOD-09 for **CAL-01** so the base case carries **calendar structure** (day-of-week ×
within-year week factors) fitted from FreshRetailNet-50K, while keeping the known-distribution thesis.
i.i.d. + daily delivery previously bought a stationary age distribution; with MWF cadence
([0109](./0109-x-11-mwf-delivery-base-case.md)) age is already only periodic — DOW demand is the
same class of re-derive, not a new kind of cost.

## Decision

We will keep **negative binomial demand known to every policy** (including every baseline), and
replace i.i.d. draws with a **day-indexed** mean profile:

- μ(day) comes from a committed FreshNet-derived product (ADR [0112](./0112-freshnet-derived-demand-product.md)).
- Dispersion: retain V/M ≈ 2.0 (MOD-26) unless the fit ticket reports an unstable refit; if
  unstable, keep `demand_vm = 2.0` and document in the fit report.
- Every policy — oracles, age-blind, SW, rollout — sees the **same** calendar NB parameters for a
  given day; no policy estimates demand.
- Runtime draws via `draw_demand(rng, params, *, day: int)` (ownership in ADR
  [0113](./0113-cal-01-track-ownership.md)); CRN still addresses `(root_seed, PHYSICS_RUN_ID, day,
  :demand)` once per day across scenarios.
- Operational scale stays near `demand_mu ≈ 30` (shape from FreshNet; absolute Chinese sales units
  are not transferred).

## Alternatives considered

- **Keep strict i.i.d. NB (ADR 0031 A)** — rejected: Oliver reopened MOD-09; calendar demand is part
  of the new base case.
- **Infer demand jointly with the state (ADR 0031 C)** — rejected: confounds forecasting with
  ordering and weakens the thesis that age information alone drives the gap.
- **Transfer FreshNet absolute sale amounts as μ** — rejected: sales are globally normalized and
  yuan economics are not transferable; scale to μ≈30.
- **Policy-specific demand forecasts** — rejected: would reintroduce forecasting as a confounder.

## Consequences

**Easy:** same known-distribution story for the post; censoring remains lossless for the filter;
CRN day keying already exists.

**Hard / cost:** protection quantiles become sums of **heterogeneous** daily NBs; age-blind weights
and α inputs must be day-indexed; fit/SKU/censoring honesty must ship with the product; prior i.i.d.
VOI cells need regeneration.

**Locked in:** known calendar NB; no joint demand inference; no runtime HF dependency.

**Revisit if:** full two-stage latent demand recovery becomes the production prior, or Oliver opens
a forecasting-vs-ordering comparison arm.

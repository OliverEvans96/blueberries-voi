# 0150. Cold-chain break events replace truncated-normal transit temperature

STATUS: ACCEPTED
DATE: 2026-08-26
BOARD-ID: MOD-11 / MOD-18 / MOD-19 / FIL
GROUP: MOD
TIER: 1
SUPERSEDES: [0144](./0144-f-native-hierarchical-arrival-model.md) (§3's
`T_bar ~ TruncNormal(mu_T, sigma_T, low=0C)` transit-temperature sub-model and the
associated 8-node thermal quadrature; the rest of 0144 — shape-scaling, the
`k·θ·η_ref = 1` reference-life calibration, the §5 conditioning table, the
`age_at_receipt` deletion — is unaffected and stays in force), [0148](./0148-abdella-derived-arrival-fit.md)
(item 1's offline fit of "truncated-normal transit temperature moments," and item 2's
`temp_floor_c` adjustment knob; the offline-fit-not-refit pattern and the other listed knobs
are unaffected)
RELATED: [0149](./0149-mod-16-three-fixed-lots-per-delivery.md) (three lots per delivery; each
lot draws its own break-event journey under that ADR's DC model), [0043](./0043-mod-21-abdella-transit-sampling-frame.md)
(MOD-21, Abdella transit sampling frame)

## Context

Two observation channels in the knowledge ladder buy almost nothing today, and in both cases
the cause is a modelling gap rather than a genuine finding. This ADR addresses the temperature
channel; ADR 0149 addresses the lot-identity channel.

**The trace is decorative, not generative.** `shipments.rs::truth_transit_trace` draws a ramp
plus jitter, then bisects a constant offset until the trace's mean temperature `φ̄` *exactly
equals the `φ̄` already drawn* from the truncated normal in `arrival.rs`. The trace is a
rendering of two scalars after the fact, not the thing the model is actually uncertain about —
and one of those two scalars barely moves: at the fitted `σ_T = 0.53 °C` (`data/abdella/arrival_model.json`),
`φ̄` has only a ~5% spread.

**Measured consequence** (`docs/findings/why-pack-date.md`, six Abdella shipments):

```
Var(log d)     = 0.205
Var(log φ̄)     = 0.00335
```

a **98.4% / 1.6%** split. A pack date is a duration measurement, so it removes 98.4% of
shipment-level exposure uncertainty on its own, and a full temperature trace can only mop up
the remaining 1.6%. This is the reason ADR 0144's F2 → F3 step measured as small: not a finding
about cold chains, but an artifact of a temperature sub-model with almost nothing left to learn
once duration is known.

**The six real shipments cannot answer the question that matters.** They are six observations
of a cold chain that *never broke*. Break frequency is therefore not estimable from them by
construction — any model that tries to fit a break rate to these six traces would be fitting
noise. The honest move is to state the break parameters as assumed, and to check the model
against the six shipments only on the regime they actually cover: the no-break limit.

**Hard constraints carried into this redesign** (per the approved plan): no meaningful increase
in per-day filter runtime, and the equations must stay simple — the truncated-normal transit
temperature is retired rather than made more elaborate.

## Decision

### 1. A break is a discrete episode, not a wider temperature draw

A **break** is a discrete episode where product leaves refrigeration: a pallet on an
unrefrigerated dock during loading, a cross-dock transfer, a reefer off with doors open, a
missed connection leaving a shipment in warm staging. Thermal damage concentrates at handoffs,
not during steady-state line-haul — hence an event model rather than "the truck ran a bit
warm."

```
N   ~ Poisson(ρ · d)                 break count; hazard constant per transit-day
τ_j ~ Exp(τ̄)   at fixed T_break     break duration (the thing that physically varies)
Λ   = (d − Στ_j)·φ_set + Στ_j·φ_break
    = d·φ_set + Σ ε_j,               ε_j = τ_j·(φ_break − φ_set)
```

The trip clock runs during a break, so the second line is **exact, not an approximation**.
Since `ε_j` is a fixed multiple of `τ_j`, it is still exponential, so given `N` the break total
is `Gamma(N, m)` — quantile-invertible with the `gamma_dist_quantile` helper already in
`arrival.rs`.

Four parameters, all in physical units: `T_set`, `T_break`, `ρ`, `τ̄`. Starting values
`T_break = 12 °C`, `τ̄ = 12 h`, `ρ = 0.08 /day` put a typical break at ~1.2 reference-days and
the duration share near 80% — down from today's 98.4%, by design, since the point of this ADR
is to give the temperature channel something real to learn.

### 2. The trace becomes the generative primitive

Lay out `K` deterministic legs with fixed duration shares and setpoints (pre-cool/staging
0.5 °C for 15%, line-haul 2 °C for 60%, dock/receiving 5 °C for 25%) — deterministic, so zero
inference cost; it only makes `φ_set` the weighted average `Σ w_k φ(T_k)`. Draw `N` break start
times uniformly on `[0, d]`, punch in rectangular pulses to `T_break` of length `τ_j` (clamped
to not overrun the trip), then compute `Λ` from the trace via the **existing**
`arrival.rs::resolve_arrival_exposure`.

This is a correctness fix, not cosmetic. Today the trace is fit *to* a pre-drawn `φ̄` by
bisection and carries no information beyond the two scalars that produced it. After this
change, `Λ` (and hence `φ̄`) is *derived from* the trace, so the trace is what's actually random
and the temperature-history observation channel is observing something real.

### 3. Deletions

The bisection loop in `truth_transit_trace`, `sample_truncated_normal`,
`truncated_normal_quantile`, `normal_cdf`, `erf`, and the `mu_T` / `sigma_T` / `temp_floor_c`
artifact fields are removed. `normal_quantile` stays — `ψ_pos` still needs it.

### 4. Filter-side cost, paid for by shrinking the sampling grid

The 8-node Gauss quadrature over the truncated normal is replaced by enumeration of `N = 0..4`
with Poisson weights, 8 nodes on `Gamma(N, m)` when `N ≥ 1` — 33 thermal nodes in place of 8.
This touches only the P0 prior build and the F2 pack-date build, both cached and paid once per
session or once per distinct integer day respectively — not a per-delivery cost. It is funded
by cutting `ARRIVAL_GRID` from 4096 to 512 (`arrival.rs`), an 8× reduction across every row, at
an inverse-sampling resolution of 0.002 in freshness — far below any noise floor in this model.

### 5. The calibration guard is re-expressed around the no-break limit

The six Abdella shipments are six observations of a chain that never broke, so `ρ` and `τ̄` are
**openly assumed**, not fit — precisely because six clean traces cannot estimate a break
frequency. The guard is re-expressed as: **at `ρ → 0` the model reproduces the six shipments'
98.4% duration share.** One model, one corridor; the guard is still checked against data, on
exactly the regime the data covers. This supersedes the unconditional duration-share guard
ADR 0144's Correction 1 introduced (`≥90% against observed 98.4%`), which implicitly assumed
`ρ = 0` without saying so; under this ADR, duration share at the *default* `ρ` is expected to
land near 80%, and the 98.4% figure is checked only as the `ρ → 0` limit.

## Alternatives considered

- **Widen `σ_T`** — rejected. A knob, not a model: it inflates the spread without any account
  of *why* a given trip ran warm, so it cannot connect to anything a domain expert or an
  investigator could reason about.
- **Per-leg Bernoulli breaks, `2^K` exactly enumerated states** — rejected. More conservative on
  compute cost (exact enumeration, no sampling), but wrong physically on two counts: break risk
  does not scale with trip length the way a per-leg Bernoulli implies, and severity becomes
  all-or-nothing (a leg either breaks entirely or not at all) rather than a duration that can be
  short or long.
- **Draw break severity as a temperature excess, `ΔT ~ Exp(6 °C)`** — rejected for a concrete
  technical reason, not a stylistic one: this makes `φ = q10^(ΔT/10)` **Pareto with tail index
  ≈ 1.5**, i.e. infinite variance and unstable quadrature. Drawing break *duration* at a fixed
  temperature avoids this entirely, because `ε_j = τ_j·(φ_break − φ_set)` is exponential (a
  fixed multiple of an exponential `τ_j`), not a power transform of one — and it tells a better
  physical story besides: a break is bounded in how hot it gets (dock temperature, ambient air)
  but unbounded in how long it can drag on (a missed connection, a stuck cross-dock).

## Consequences

**Makes easy.** The temperature-history channel becomes genuinely informative: `φ̄`'s share of
exposure variance rises from ~1.6% (today) to a design target near 20% at default `ρ`, so F3 has
something real to learn beyond de-rounding the pack date. The trace is the generative primitive,
so `Λ` is derived from something actually random rather than fit to a scalar by bisection.

**Makes hard / costs.** Every duration-share number downstream of the six-shipment calibration
note changes meaning: it now depends on `ρ`, and the headline 98.4% figure survives only as a
limiting case (`ρ → 0`), not as the working default. `scripts/fit_abdella_arrival.py` and
`scripts/arrival_calibration_note.py` both need to fit/report corridor duration gammas without
also fitting truncated-normal temperature moments, and to report the new break parameters
alongside an explicit statement that `ρ` and `τ̄` are assumed, not fit. Notebook 13's ladder
numbers need a fresh run; the F2 → F3 step is expected to grow beyond its current near-halving.

**Runtime.** Thermal node count (8 → 33) touches only the P0 prior and F2 pack-date builds —
cached, startup-only. ADR 0149's three-lots-per-delivery touches only the F3 trace build (3×
more builds per delivery, since `Λ` is continuous and the cache never hits there anyway). Both
are funded by the `ARRIVAL_GRID` cut from 4096 to 512.

**Locks in.** Break events (`Poisson` count × `Exp` duration at fixed `T_break`) as the sole
thermal stochastic mechanism, replacing the truncated-normal mean-temperature draw. The
temperature trace as the generative primitive that `Λ` is derived from, not a rendering fit to
a pre-drawn scalar. `ρ → 0` reproducing the observed 98.4% duration share as the calibration
guard's binding condition. Everything else ADR 0144 settled — shape-scaling, `k·θ·η_ref = 1`,
the §5 conditioning table, `age_at_receipt`'s deletion — is unaffected and remains in force.

**Revisit if.** Real corridor logger data ever accumulates enough breaks to actually estimate
`ρ` and `τ̄` rather than assume them; or break *severity* (not just duration) turns out to
matter, which would need a different tail-safe severity law than the one rejected above.

# 0150. Cold-chain break events replace truncated-normal transit temperature

STATUS: ACCEPTED (baseline amended 2026-08-26 by T-163 — transit generative v2)
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

a **98.4% / 1.6%** split under the *old* truncated-normal sub-model. A pack date is a duration
measurement, so it removes most shipment-level exposure uncertainty on its own, and a full
temperature trace can only mop up the remainder. This is the reason ADR 0144's F2 → F3 step
measured as small: not a finding about cold chains, but an artifact of a temperature sub-model
with almost nothing left to learn once duration is known.

**The six real shipments cannot answer the question that matters.** They are six observations
of a cold chain that *never broke*. Break frequency is therefore not estimable from them by
construction — any model that tries to fit a break rate to these six traces would be fitting
noise. The honest move is to state the break parameters as assumed, and to check the model
against the six shipments only on the regime they actually cover: the no-break limit.

**Hard constraints carried into this redesign** (per the approved plan): no meaningful increase
in per-day filter runtime, and the equations must stay simple — the truncated-normal transit
temperature is retired rather than made more elaborate.

**T-163 amendment (transit generative v2).** A partial implementation landed deterministic
fixed leg shares plus breaks. That scaffold is insufficient: at `ρ → 0` a fully deterministic
baseline makes `φ̄` a function of duration only (100% duration share), so the original guard
"reproduce 98.4% duration share at `ρ → 0`" is unachievable. The accepted generative story is
now bottom-up Abdella-matched stage durations, a trip-wide cool/nominal/warm thermal mode,
required hourly OU on the path, and 0150-style breaks — with a closed-form filter projection
that mixes modes × stage-gamma baseline × Poisson–gamma breaks (no hourly latent in the filter).

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

Four break parameters, all in physical units: `T_set` (from the legged baseline), `T_break`, `ρ`,
`τ̄`. Starting values `T_break = 12 °C`, `τ̄ = 12 h`, `ρ = 0.08 /day` put a typical break at
~1.2 reference-days. At default `ρ`, duration vs break share of `Var(log Λ)` is a **design**
output (~80% duration target from the original plan is acceptable as a scenario number, not an
Abdella measurement).

### 2. The trace becomes the generative primitive (transit generative v2)

**Bottom-up durations (exact Abdella match).** Let the pooled Abdella law be the sole duration
family (`corridors.abdella_all`):

```
d = d_min + E,   E ~ Gamma(a, b)
```

with committed fit `(d_min, a, b) ≈ (1.853, 3.009, 0.974)`. Draw stages first:

```
e_k ~ Gamma(w_k · a, b)   i.i.d. scale b
d_k = w_k · d_min + e_k
d   = Σ_k d_k
```

Then `d` has **exactly** the Abdella pooled law. Short/long haul are outcomes of the draw, not
first-class studio modes.

**Trip thermal mode.** Once per trip draw discrete mode `M ∈ {cool, nominal, warm}` with
probabilities `(p_c, p_n, p_w)` and fixed offsets `δ_c < δ_n = 0 < δ_w`. Stage setpoints are
`T_k^mean = μ_k + δ_M` for nominal stage means `μ_k` and shares `w_k` (pre-cool/staging
0.5 °C / 15%, line-haul 2.0 °C / 60%, dock/receiving 5.0 °C / 25%).

**Hourly noise (required on path).** Around each stage mean, OU / AR(1) noise with correlation
time ≈ 1 hour (fixed) and amplitude `σ_hour` (one assumed knob). Must be visible on Events
delivery-temperature charts even when `ρ = 0`.

**Breaks (unchanged).** Draw `N ~ Poisson(ρ · d)`, punch rectangular pulses at fixed
`T_break` of length `τ_j ~ Exp(τ̄)` (clamped so total break time ≤ `d`). Pack date is total
calendar duration; breaks sit *inside* it.

**Path assembly.** Emit `ShipmentTrace` `{times_d, temps_c}`; compute `Λ` via existing
`arrival.rs::resolve_arrival_exposure`. Per-unit birth uses existing `ψ` and shelf gamma APIs.

This is a correctness fix, not cosmetic. Today the trace is fit *to* a pre-drawn `φ̄` by
bisection and carries no information beyond the two scalars that produced it. After this
change, `Λ` (and hence `φ̄`) is *derived from* the trace, so the trace is what's actually random
and the temperature-history observation channel is observing something real.

### 3. Deletions

The bisection loop in `truth_transit_trace`, `sample_truncated_normal`,
`truncated_normal_quantile`, `normal_cdf`, `erf`, and the `mu_T` / `sigma_T` / `temp_floor_c`
artifact fields are removed. `normal_quantile` stays — `ψ_pos` still needs it. Studio chips
`short_haul` / `long_haul` are demoted — one unified transit law.

### 4. Filter projection (closed-form; no hourly latent)

Particles never store paths. Arrival laws stay in `ArrivalModel` caches (`Prior`, `Duration(d)`,
`Exposure(Λ)`).

**Baseline exposure given mode.** With effective rates `φ_eff(T) = E[φ(T + X_OU)]` (Jensen fold of
hourly noise; OU is not a filter latent):

```
Λ_base | M = Σ_k d_k · φ_eff(μ_k + δ_M) = c_M + Σ_k φ_eff(μ_k + δ_M) · e_k
```

Each `φ_k · e_k` is gamma with scale `b · φ_k`. Default: moment-match the sum to one
`Gamma(a_M*, b_M*)` per mode; upgrade to DP/FFT convolution on a fixed `Λ` grid if coherence
fails.

**Breaks.** Enumerate `N = 0..N_max` (keep 4), Poisson weights on `ρ · d`, for `n ≥ 1` use
8-node quadrature on `Gamma(n, m_M)` with `m_M = τ̄ · (φ_break − φ_eff,M)`, cap by trip.

**Mode mix.**

```
P(Λ | d) = Σ_M p_M · P(Λ_base + Λ_break | d, M)
```

Node budget: `3 × (1 + N_max × 8)` thermal nodes per `d`, plus duration×position outer quads
for prior — cached, milliseconds-class, not per particle-day. `ARRIVAL_GRID` remains 512.

### 5. The calibration guard is re-expressed (ρ → 0 clean-chain moments)

The six Abdella shipments are six observations of a chain that never broke, so `ρ` and `τ̄` are
**openly assumed**, not fit. The binding guards are:

1. **Duration:** simulated `d` matches the Abdella law; `Var(log d) ≈ 0.205` (bottom-up stage
   gammas preserve the pooled marginal exactly).
2. **Clean chain (`ρ → 0`):** mean and SD of `φ̄` (and mean `Λ`) match the six shipments within
   agreed tolerances — mild scatter restored by trip modes + hourly OU, not by widening a
   truncated normal.
3. **Coherence:** Monte Carlo generative `Λ | d` moments match filter `Duration(d)` within
   tolerance (§2.6 of `.team/plans/arrival-transit-generative-v2.md`).

The **withdrawn** guard is: "at `ρ → 0` reproduce the 98.4% duration share." That figure is a
*diagnostic of the old model*, not a target under a generative path with modes and OU. At
default `ρ`, duration share of `Var(log Λ)` near ~80% remains an acceptable design scenario.

## Alternatives considered

- **Widen `σ_T`** — rejected. A knob, not a model: it inflates the spread without any account
  of *why* a given trip ran warm, so it cannot connect to anything a domain expert or an
  investigator could reason about.
- **Deterministic fixed leg shares only (partial Stage 1)** — rejected as the final thermal
  design. At `ρ → 0` exposure collapses to a function of duration only; cannot restore clean-chain
  `φ̄` scatter or pass coherence with informative F3.
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
- **Hourly OU inside live filter quadrature** — rejected. Path realism without exploding per-day
  filter cost; Jensen-folded `φ_eff` in the baseline is sufficient if coherence passes.

## Consequences

**Makes easy.** The temperature-history channel becomes genuinely informative: trip modes, hourly
OU, and breaks give F3 real thermal variance a pack date cannot see. The trace is the generative
primitive, so `Λ` is derived from something actually random rather than fit to a scalar by
bisection. One unified duration family simplifies studio UX.

**Makes hard / costs.** Every duration-share number downstream of the six-shipment calibration
note changes meaning: headline 98.4% survives only as a property of the *retired* truncated-normal
model, not as a `ρ → 0` guard. `scripts/fit_abdella_arrival.py` fits duration moments only;
modes, `σ_hour`, and break parameters are assumed with provenance. Notebook 13's ladder numbers
need a fresh run; the F2 → F3 step is expected to grow beyond its current near-halving.

**Runtime.** Thermal node count rises (modes × baseline × breaks) but touches only P0 and F2 —
cached, startup-only. ADR 0149's three-lots-per-delivery touches only the F3 trace build (3×
more builds per delivery). Both are funded by `ARRIVAL_GRID` 512.

**Locks in.** Break events (`Poisson` count × `Exp` duration at fixed `T_break`) as a thermal
stochastic mechanism alongside trip modes and path OU — replacing the truncated-normal
mean-temperature draw. The temperature trace as the generative primitive that `Λ` is derived
from. Filter projection as mode-mixed stage-gamma baseline plus Poisson–gamma breaks, with no
hourly filter latent. Calibration at `ρ → 0` on `Var(log d)` and clean-chain `φ̄` moments, plus
generative/filter coherence — not on the old 98.4% duration-share figure. Everything else ADR
0144 settled — shape-scaling, `k·θ·η_ref = 1`, the §5 conditioning table, `age_at_receipt`'s
deletion — is unaffected and remains in force.

**Revisit if.** Real corridor logger data ever accumulates enough breaks to actually estimate
`ρ` and `τ̄` rather than assume them; or break *severity* (not just duration) turns out to
matter, which would need a different tail-safe severity law than the one rejected above.

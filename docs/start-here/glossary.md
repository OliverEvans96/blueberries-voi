---
title: Notation and glossary
sources:
  code: [crates/voi_core/src/params.rs, crates/voi_core/src/arrival.rs, crates/voi_core/src/physics.rs, crates/voi_core/src/policy.rs, crates/voi_core/src/session.rs, crates/voi_core/src/demand_profile.rs]
---

# Notation and glossary

This site reuses a small set of symbols on almost every page. Rather than redefine
them each time, they're collected here — look a symbol up once, then read the rest
of the site without breaking stride. Every entry below is checked against the
current Rust source, and defaults are the values `ModelParams::default()` ships
with.

![Cheat sheet: where f, Λ, φ̄, d, and ψ live on corridor → truck → shelf → sale](/figures/glossary-symbol-journey.png)

## State and physics

| Symbol | Meaning |
| --- | --- |
| $f$ | **Freshness** — a unit's remaining-quality state, $f \in [0, 1]$. $1$ = pristine, $0$ = spoiled/dead. This is the one state variable the whole model tracks per unit; it is never called "age." |
| $\Lambda$ | **Cumulative thermal exposure** of a shipment's journey, in reference-days. Per unit, $\Lambda = d \cdot \bar\varphi \cdot \psi$. It's a property of the *trip*, not something the fruit "carries" as an age. |
| $\bar\varphi$ | **Duration-averaged Q10 temperature factor** of a journey or a day: $\bar\varphi = q_{10}^{(\bar T - T_\mathrm{ref})/10}$. |
| $d$ | **Calendar transit duration**, in days, for one delivery — a shifted-gamma random variable: $d = d_\mathrm{min} + \mathrm{Gamma}(\text{delay\_shape}, \text{delay\_scale})$. |
| $\psi$ | **Within-pallet position multiplier**, drawn per unit as $\mathrm{LogNormal}(0, \sigma_\mathrm{pos})$. It is never directly observed by anything on the knowledge ladder. |
| $\eta_\mathrm{ref}$ | **Reference life** — shelf life in reference-days at the reference temperature $T_\mathrm{ref}$. Default: **14 days at 0 °C**. |
| $k$ | **Gamma-process shape parameter**, shared by transit and in-store aging. Default: **2.0**. |
| $\theta$ | **Gamma-process scale parameter**, derived so $k\theta\eta_\mathrm{ref} = 1$. Default: **1/28** (≈0.0357) given the defaults above. |
| $q_{10}$ | **Rate multiplier per 10 °C** of temperature: how much faster things age when warmer. Default: **3.0**. |
| $\sigma$ | **Picking-weight exponent** — a customer's chance of picking a given unit is proportional to $f^\sigma$. Default: **0.5**; $\sigma = 0$ would make picking uniform/random. |

## Control and inventory

| Symbol | Meaning |
| --- | --- |
| $\alpha$ | The **target service-level quantile** used by the ordering policy. Default: **0.9**. This is a *tuned* dial, not the textbook newsvendor critical fractile. |
| $\rho$ | **Damping factor** on the ordering rule. Default: **0.8**. |
| $\tilde{I}$ | **Effective inventory** — quality-weighted on-hand units. Each unit counts as its expected freshness, not as a flat $1$. |
| $L$ | Number of most-recent **lots** exported to the belief wire for charts/policy. Default: **10**. |
| $K$ | Number of freshness histogram bins per lot on the belief wire. |
| $U$ | Max units per lot slot in the internal grid (`units_per_lot`). Default: **15**. |
| $\mu(\text{day})$ | The calendar demand profile's mean for a given day: $\mu(\text{day}) = \text{scale} \times \text{dow\_factor}[\text{day} \bmod 7] \times \text{week\_factor}[\lfloor \text{day} / 7 \rfloor]$. |

## Vocabulary

| Term | Meaning |
| --- | --- |
| **rung** | One named point on the observation ladder (`P0`, `P1`, `F1`, `F1s`, `F2a`, `F2`, `F3`): a preset combination of what's observed. |
| **corridor** | A named arrival lane / transit-parameter set (e.g. `abdella_all`, `short_haul`, `long_haul`). |
| **lot** | One delivery's cohort of units, tracked together from arrival through sale, spoilage, or retirement. |
| **unit** | One saleable item (one clamshell/punnet) with its own freshness value. |

## A word this site does not use

This site avoids "age" or "effective age" for a unit's state. The model tracks
**freshness** $f$ directly, running from 1 down to 0. Two helper functions,
`age_to_f` and `f_to_age`, exist in the code to convert between the two
representations for a separate research path, but they are not part of how the
production model or the filter represents state.

## Caveats

This page is a reference, not an argument — it doesn't explain *why* these
parameters take these forms or these defaults. See
[Freshness, not age](/store/freshness-not-age),
[The cold chain](/store/cold-chain-arrival), and
[Effective inventory](/control/effective-inventory) for the reasoning behind the
entries above. A few symbols used deeper in the site (demand overdispersion, the
particle count, rollout costs) aren't listed here because they weren't part of
this page's brief — check the relevant page's own "The math" section for those.

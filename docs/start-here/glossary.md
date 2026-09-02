---
title: Notation and glossary
sources:
  code: [crates/voi_core/src/params.rs, crates/voi_core/src/arrival.rs, crates/voi_core/src/physics.rs, crates/voi_core/src/policy.rs, crates/voi_core/src/session.rs, crates/voi_core/src/demand_profile.rs]
---

# Notation and glossary

This site reuses a small set of symbols on almost every page. Rather than redefine
them each time, they're collected here — look a symbol up once, then read the rest
of the site without breaking stride. Every entry below is checked against the
current code, and the defaults shown are the values the model ships with out of
the box, before any tuning.

## State and physics

| Symbol | Meaning |
| --- | --- |
| $f$ | **Freshness** — a unit's remaining-quality state, $f \in [0, 1]$. $1$ = pristine, $0$ = spoiled/dead. This is the one state variable the whole model tracks per unit; it is never called "age." |
| $\Lambda$ | **Cumulative thermal exposure** — how much heat stress a shipment has racked up over its journey, measured in reference-days (the fraction of a unit's shelf life the trip effectively "used up" at the reference temperature). Per unit, $\Lambda = d \cdot \bar\varphi \cdot \psi$. It's a property of the *trip*, not something the fruit carries around as an age. |
| $\bar\varphi$ | **Duration-averaged temperature factor** — how much faster than the reference temperature a journey or a day is running, on average: $\bar\varphi = q_{10}^{(\bar T - T_\mathrm{ref})/10}$. This follows an Arrhenius-style rule from food science: spoilage roughly multiplies by $q_{10}$ for every 10°C rise in temperature (see $q_{10}$ below). |
| $d$ | **Calendar transit duration**, in days, for one delivery — a minimum duration plus a random draw from a Gamma distribution (a smooth decay-shaped curve), with its own shape and scale separate from the freshness-decay process below: $d = d_{\min} + \mathrm{Gamma}(k_d, \theta_d)$. |
| $\psi$ | A per-unit multiplier reflecting that units from the same lot don't all arrive at exactly the same freshness. Drawn as $\mathrm{LogNormal}(0, \sigma_\mathrm{pos})$, where $\sigma_\mathrm{pos}$ is the **inter-lot position noise** (default: **0.08**). It is never directly observed by anything on the observation ladder. |
| $\eta_\mathrm{ref}$ | **Reference life** — shelf life in reference-days at the reference temperature $T_\mathrm{ref}$. Default: **14 days at 0°C**. |
| $k$ | **Gamma-process shape parameter** — controls how "bunched up" spoilage is versus spread out smoothly. Shared by transit and in-store freshness loss. Default: **2.0**. |
| $\theta$ | **Gamma-process scale parameter**, derived so $k\theta\eta_\mathrm{ref} = 1$. Default: **1/28** (≈0.0357) given the defaults above. |
| $q_{10}$ | **Rate multiplier per 10°C** of temperature — an Arrhenius-style rule from food science: spoilage roughly multiplies by $q_{10}$ for every 10°C rise in temperature. Default: **2.0**. |
| $\sigma$ | **Picking-weight exponent** — a customer's chance of picking a given unit is proportional to $f^\sigma$, so shoppers lean toward fresher units without strictly always taking the freshest. Default: **0.5**; $\sigma = 0$ would make picking uniform/random. |

## Control and inventory

| Symbol | Meaning |
| --- | --- |
| $\alpha$ | The target **service level** used by the ordering policy — roughly, the probability of not running out of stock before the next order arrives. Default: **0.9**. This is a tuned dial, not derived from a fixed inventory-theory formula. |
| $\rho$ | **Damping factor** on the ordering rule — how strongly it reacts to the gap between the target and the effective inventory (see $\tilde I$ below). Default, before any tuning: **0.8**. (Elsewhere on the site, this value is refit per scenario during experiments — see the results pages for those tuned numbers; don't confuse the two.) |
| $\tilde{I}$ | **Effective inventory** — quality-weighted on-hand units. Each unit counts toward the total as its expected freshness, not as a flat $1$. |
| $L$ | Number of most-recent **lots** exported to the belief wire for charts and policy use. Default: **50**. |
| $K$ | Number of freshness histogram bins per lot on the belief wire. |
| $U$ | Max units per lot slot in the internal simulation grid. Default: **15**. |
| $\mu(\text{day})$ | The calendar demand profile's mean for a given day. Demand follows a weekly rhythm (weekdays differ from weekends) and a slower seasonal one (some weeks of the year are busier than others). We capture that as: mean demand equals a baseline scale, times a day-of-week multiplier, times a week-of-year multiplier — $\mu(\text{day}) = \mu_0 \times d(\text{day} \bmod 7) \times w(\lfloor \text{day} / 7 \rfloor)$, where $\mu_0$ is the baseline daily mean, $d(\cdot)$ is the day-of-week multiplier, and $w(\cdot)$ is the week-of-year multiplier. |

## Vocabulary

| Term | Meaning |
| --- | --- |
| **observation scenario** | One named point on the observation ladder: a preset combination of what's observed (for example "books only," "the pack-date scenario," or "the LGTIN scenario" — see the ladder itself on the [Freshness, not age](/store/freshness-not-age) page). |
| **corridor** | The shipping-route / transit-assumption profile a delivery uses — either one of six real refrigerated shipments used to calibrate transit timing, or a generic short-haul or long-haul preset. |
| **lot** | One delivery's cohort of units, tracked together from arrival through sale, spoilage, or retirement. |
| **unit** | One saleable item (one clamshell/punnet) with its own freshness value. |

## A word this site does not use

This site avoids "age" or "effective age" for a unit's state. The model tracks
**freshness** $f$ directly, running from 1 down to 0. A couple of helper
functions exist in the code to convert between the two representations, kept
around for a separate research path — but they are not part of how the
production model or the filter represents state.

## Caveats

This page is a reference, not an argument — it doesn't explain *why* these
parameters take these forms or these defaults. See
[Freshness, not age](/store/freshness-not-age),
[The cold chain](/store/cold-chain-arrival), and
[Effective inventory](/control/effective-inventory) for the reasoning behind the
entries above. A few symbols used deeper in the site (demand overdispersion, the
particle count, rollout costs) aren't covered on this page — check the relevant
page's own "The math" section for those.

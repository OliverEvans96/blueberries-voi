---
title: No channel ever observes freshness
sources:
  code:
    [
      crates/voi_core/src/arrival.rs,
      crates/voi_core/src/unit_pf.rs,
      crates/voi_core/src/obs.rs,
      crates/voi_core/src/physics.rs,
    ]
---

# No channel ever observes freshness

Even the richest scenario on the [ladder](./observation-scenarios.md) — the
temperature-history scenario, where a logger rides along with the pallet and records the
whole trip — never hands the filter a freshness number. It hands a *duration*, or a
running total of heat exposure. Freshness itself, written $f$, depends on things no
sensor in this model reads: exactly where a unit sat inside the pallet, and how that
particular unit's own spoilage happened to run. That's why the internal record that
carries a day's observations to the filter has no freshness-valued field at all — there
is nothing in what any channel reports for such a field to hold.

## The idea

Picture a pallet of blueberries leaving the farm. Two different instruments could ride
along with it:

- A **pack-date stamp** tells you when the pallet was packed. Compared against today's
  date, that's a *calendar duration* — five days, say. It says nothing about how cold the
  truck actually ran.
- A **temperature logger** tells you the truck's temperature at every point along the
  route. Integrated over the trip, that's a *cumulative thermal exposure* — a single
  number that combines how long the trip took **and** how much heat stress it involved.

Neither one is a freshness reading. A five-day trip in a well-run refrigerated truck
barely stresses the fruit; a five-day trip with the cooling system cycling badly can
spoil it outright. So even after you observe the pack date — or the full temperature
trace — you still don't know the fruit's freshness. You know one input to it. What
you're left holding is a *distribution* over freshness: a spread of plausible values,
never a single number. That spread reflects everything else you still don't know —
exactly how cold the truck ran on average, and, because a pallet isn't all one
temperature, where inside it any given unit happened to sit. Combine what you did
observe with the model's prior over everything you didn't, and that spread is exactly
what you get.

That's also why upgrading the delivery-history channel (none → pack date → temperature
history) narrows this spread rather than replacing a guess with a fact. The
temperature-history level pins down the most about the journey, but it still can't tell
you which units in the pallet sat in the coldest corner versus the warmest, or which
units happened to spoil a little faster than their neighbors for reasons no sensor
tracks.

## The math

The arrival model generates a unit's freshness through a short chain of unobserved and
partly-observed quantities:

- $d$ — the **calendar transit duration** in days: time from pack to arrival.
- $\bar T$ — the shipment's mean transit temperature — and $\bar\phi$ — the corresponding
  **duration-averaged Q10 temperature factor**. Q10 is an Arrhenius-style rule from food
  science: spoilage roughly multiplies by Q10 for every 10°C rise in temperature.
  $\bar\phi = q_{10}^{(\bar T - T_{\text{ref}})/10}$, where $q_{10}$ is that multiplicative
  factor and $T_{\text{ref}}$ is the reference temperature.
- $\psi$ — a **within-pallet position multiplier**, drawn independently per unit,
  capturing that a unit in the coldest corner of the pallet loses freshness more slowly
  than one in the warmest.
- $\Lambda$ — the **cumulative thermal exposure**, in reference-days:
  $$
  \Lambda = d \cdot \bar\phi \cdot \psi.
  $$
  $\Lambda$ is a property of the *journey a unit took*, never something the fruit itself
  carries.
- A per-unit gamma draw converts $\Lambda$ into freshness: $f = \max(0, 1 - D)$ where $D
  \sim \mathrm{Gamma}(k \Lambda, \theta)$, so
  $$
  P(f > x \mid \Lambda) = \gamma_p(k \Lambda, (1-x)/\theta), \qquad
  P(f = 0 \mid \Lambda) = \gamma_q(k \Lambda, 1/\theta),
  $$
  using the regularized incomplete gamma functions $\gamma_p$ and $\gamma_q$.

No observation channel ever reports $f$, $\psi$, or the per-unit gamma draw directly.
What a channel reports determines how much of this chain gets pinned down before the
remaining pieces are integrated out. When there's no delivery history at all, the model
falls back to the **corridor** — the general shipping-route and transit-time assumptions
built into that lane — instead of anything specific to this shipment:

| Delivery history | Observes | Conditions on | Integrates over |
| --- | --- | --- | --- |
| Temperature history | the full trace — timestamps **and** temperatures | $\Lambda$ (both $d$ and $\bar\phi$ together) | $\psi$, the per-unit gamma draw |
| Pack date | pack date | $d$ only | $\bar T$ (hence $\bar\phi$), $\psi$, the per-unit gamma draw |
| None | nothing about the delivery | the corridor's default assumptions only | $d$, $\bar T$, $\psi$, the per-unit gamma draw |

Whatever is "integrated over" in that table is exactly the source of the residual spread
described above — it is not approximation error, it is the honest consequence of a
variable no observation scenario ever measures.

## Why it's modelled this way

A date reveals a *calendar duration*. Freshness is derived by combining that duration
with the modeled temperature distribution, which yields a **distribution** over
freshness values, not a single number. That distribution, not a scalar, is what seeds
the lot. Letting a delivery observation collapse straight to a single freshness number
(a *point mass* — all the probability concentrated on one value, with no spread) would
silently discard real uncertainty: every observation scenario would then end up
producing very similar beliefs, because the one place where richer information should
sharpen the belief would instead be thrown away at the conversion step. Keeping the full
distribution is what lets richer channels actually produce a measurably sharper belief.

**Alternative rejected — converting an observed duration straight into a single
freshness number.** An earlier design considered measuring how long a unit had been in
transit and converting that duration directly into one freshness value. That conversion
collapses everything onto a single point, which conflicts with the principle above: it
would silently discard the very uncertainty a richer channel is supposed to reveal. This
approach isn't used by any current observation scenario — it survives only as a
separate, non-production research path (see the fields and helpers listed in the table
below).

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Channel-conditional arrival law, mutually exclusive cases | `enum ArrivalCondition { Exposure(f64), Duration(i32), Prior }` | `crates/voi_core/src/arrival.rs:75` |
| Temperature-history case: conditions on the full exposure $\Lambda$ | `ArrivalCondition::Exposure(f64)` | `crates/voi_core/src/arrival.rs:77` |
| Pack-date case: conditions on duration $d$ only | `ArrivalCondition::Duration(i32)` | `crates/voi_core/src/arrival.rs:79` |
| No-delivery-history case: corridor default only | `ArrivalCondition::Prior` | `crates/voi_core/src/arrival.rs:81` |
| Exact $\Lambda$ from an observed trace (the temperature-history integral) | `resolve_arrival_exposure(obs_temps, obs_times, q10, t_ref)` | `crates/voi_core/src/arrival.rs:2334` |
| $P(f>x \mid \Lambda)$ / $P(f=0 \mid \Lambda)$ | `ArrivalModel::p_f_gt_at`, `ArrivalModel::p_f_zero` | `crates/voi_core/src/arrival.rs:1297`, `crates/voi_core/src/arrival.rs:1324` |
| $\bar\phi = q_{10}^{(\bar T - T_{\text{ref}})/10}$ | `store_temp_factor(t_store_c, t_ref_c, q10)` | `crates/voi_core/src/physics.rs:38` |
| Filter's own choice of condition, per-day, from the day's observation record | `resolve_arrival_f_law(obs, q10, t_ref)` | `crates/voi_core/src/unit_pf.rs:298` |
| No freshness-valued field on the wire | `struct FilterObs { .. temp_times_d, temp_temps_c, pack_date_days .. }` (no `f` field) | `crates/voi_core/src/obs.rs:90` |
| Rejected design: observed duration converted straight to a freshness scalar (`ObsMask::age_at_receipt`, `RichDay::age_at_receipt`, `FilterObs::age_at_receipt`, `f_at_receipt_from_age`, `birth_f_f2_dirac`) — none of this is on the live path | — | `crates/voi_core/src/obs.rs`, `crates/voi_core/src/physics.rs` |
| Retired duration↔freshness mapping (legacy Weibull — a smooth decay curve — salvage path only, not a production observation scenario) | `age_to_f`, `f_to_age` | `crates/voi_core/src/physics.rs:19`, `crates/voi_core/src/physics.rs:30` (used at `crates/voi_core/src/rollout.rs:111`) |

## Caveats

- $\psi$ (within-pallet position) and the per-unit gamma draw are **never** observed by
  any observation scenario, including the richest one — the temperature-history
  scenario, which also carries an LGTIN (a lot-level identifier that pins the shipment
  down to one production batch of one product) and a pack date. That is a deliberate
  floor on how sharp belief can ever get — and part of the reason units within one lot
  arrive with genuinely different freshness — not a gap this project intends to close
  with a richer channel.
- The whole arrival chain models the **refrigerated leg only**. The harvest-to-precool
  field-heat window before refrigeration starts is out of scope, so the freshness this
  model reports at arrival is an upper bound — real arrival freshness is likely somewhat
  lower than what any observation scenario, including the richest one, would infer.
- The conditional laws ($P(f>x\mid\Lambda)$, the $d$-marginal for the pack-date case) are
  built from **assumed parametric families calibrated by hand against six shipments**,
  not fit by maximum likelihood — six shipments is not enough data to support a fitted
  claim. Treat the shape of these distributions as a documented modeling choice, not a
  measured fact about the actual cold chain.

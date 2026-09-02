---
title: How fruit loses freshness — the gamma process
sources:
  code: [crates/voi_core/src/physics.rs, crates/voi_core/src/params.rs]
---

# How fruit loses freshness: the gamma process

Every day a unit sits on the shelf (or rides in the truck), it loses a random amount of freshness — not a fixed amount, a random one, drawn fresh each day, whose size depends on that day's temperature. This is the physical engine underneath the whole model: everything the store believes, orders, and eventually sells or throws away traces back to how this daily loss is drawn.

## The idea

Think of freshness loss as small setbacks piling up over a day — a bit of moisture lost here, a bruise starting there, a spot where mould gets a foothold. Warmer temperatures don't make each setback bigger; they make setbacks happen more often. A day at room temperature isn't a day in the fridge with the damage turned up in volume — it's more like several fridge-days of setbacks compressed into one day.

That distinction matters for predictability. If heat made each setback bigger but not more frequent, a very hot day would be volatile — one lucky roll and the fruit is nearly fine, one unlucky roll and it's ruined, with about the same relative uncertainty as a cold day. If heat instead makes setbacks more frequent, the small setbacks average out more over a hot day, so the outcome becomes *more* predictable in relative terms — more events means less relative noise, the same way a coin flipped 100 times settles closer to 50/50 than a coin flipped 10 times. This model takes the second view, because it matches how Q10 — an Arrhenius-style rule from food science, where spoilage roughly multiplies by Q10 for every 10°C rise in temperature — is normally understood: temperature governs how often a molecular-level event fires, not how big it is when it fires.

The practical upshot: hotter storage means a bigger average daily loss, *and* a wider daily loss, growing together. A punnet at 4°C loses a little freshness with fairly predictable regularity; the same punnet at 12°C loses much more, and the outcome varies more too.

## The math

Each unit's daily freshness decrement $\Delta$ is drawn from a Gamma distribution:

$$
\Delta \sim \mathrm{Gamma}(k \cdot \bar\phi,\ \theta), \qquad f_{\text{next}} = \max(f - \Delta,\ 0)
$$

where:
- $k$ is the base gamma shape parameter (a fixed constant of the model),
- $\theta$ (theta) is the gamma scale parameter (also fixed),
- $\bar\phi$ (phi-bar) is the duration-averaged Q10 temperature factor for the current temperature, and
- $f$ is the unit's freshness before the day, clamped at 0 (once a unit hits 0 it's spoiled and stays there).

$\bar\phi$ itself comes from the Arrhenius-style Q10 rule:

$$
\bar\phi = q_{10}^{\,(T_\text{store} - T_\text{ref})/10}
$$

where $T_\text{store}$ is the storage temperature (°C), $T_\text{ref}$ is a fixed reference temperature, and $q_{10}$ is the multiplicative factor by which the rate of freshness loss increases for every 10°C of warming.

The key modeling choice is *where* $\bar\phi$ enters the Gamma distribution: it multiplies the **shape** parameter $k$, not the **scale** parameter $\theta$. This is "shape-scaling." Because a Gamma$(k, \theta)$ distribution has mean $k\theta$ and variance $k\theta^2$, shape-scaling by $\bar\phi$ multiplies *both* the mean and the variance of $\Delta$ by $\bar\phi$ — a hotter day means proportionally more loss and proportionally more spread, together, matching the "more frequent small events" story above. The alternative, scale-scaling ($\mathrm{Gamma}(k, \theta \cdot \bar\phi)$), would multiply the mean by $\bar\phi$ but the variance by $\bar\phi^2$ — meaning *relative* uncertainty would stay exactly the same at any temperature, as if heat only ever made individual events bigger, never more frequent.

Transit is the same law integrated over the trip rather than looped once per day: cumulative thermal exposure $\Lambda$ (reference-days; see [Freshness, not age](/store/freshness-not-age)) plays the role that $\bar\phi$ plays for a single day, and the loss over the whole trip is $D \sim \mathrm{Gamma}(k\Lambda,\ \theta)$, with arrival freshness $f = \max(1 - D,\ 0)$.

**Reference-life invariant.** The model pins down $k$, $\theta$, and the reference shelf life $\eta_\text{ref}$ (eta-ref, in reference-days) with one identity:

$$
k \cdot \theta \cdot \eta_\text{ref} = 1
$$

so that $k\theta$ — the expected freshness loss per reference-day — equals exactly $1/\eta_\text{ref}$, regardless of how $k$ or $\eta_\text{ref}$ individually get tuned. With the model's default values ($k = 2.0$, $\eta_\text{ref} = 14.0$ reference-days at $T_\text{ref} = 0°\text{C}$), that invariant gives $\theta = 1/(k\eta_\text{ref}) = 1/28 \approx 0.0357$, so one reference-day of exposure costs exactly $k\theta = 1/14 \approx 0.0714$ of freshness — about $7.1\%$ — no matter what temperature path produced that reference-day.

The other default values: $q_{10} = 2.0$ (freshness loss doubles for every 10°C of warming) and a default store temperature $T_\text{store} = 4°\text{C}$ (the interactive slider runs roughly $0$–$12°\text{C}$).

## Why it's modelled this way

**Shape-scaling, not scale-scaling.** Two structural properties of the model depend on this choice:

1. **$\Lambda$ is a sufficient statistic only under shape-scaling** — meaning it's a single summary number that captures everything relevant, with nothing lost by using it in place of the full temperature record. Tracking cumulative thermal exposure $\Lambda$ as one number, rather than the full minute-by-minute temperature trace, only works if $\Lambda$ alone is enough to determine the resulting freshness distribution. Under shape-scaling that's true: two journeys with the same $\Lambda$ but different temperature paths end up with the same freshness distribution. Under scale-scaling it's false. Two such journeys would share a mean but differ in variance, so summarizing a trip by $\Lambda$ alone would throw away information — and the temperature-history scenario in [the observation ladder](/ladder/channels), which reads a full temperature log, would be wrong to claim it already knows the arrival freshness distribution from $\Lambda$ alone.
2. **Only shape-scaling is timestep-invariant.** Gamma processes are *infinitely divisible*: one long Gamma draw over an entire transit leg, and many small daily Gamma draws over that same elapsed exposure at the same temperature, are the same underlying process viewed at different granularities. Under shape-scaling this holds — transit modeled as one continuous exposure and shelf life modeled as a daily loop are reconcilable as the same law. Under scale-scaling, the accumulated variance would depend on how finely you chopped up the time axis. That would make the model's answers depend on an arbitrary implementation choice — how often the simulation loop ticks — rather than on the physics.

**Honest caveat.** The gamma process itself is an idealization. Real berry loss is partly *discrete* — a single bruise, or mould spreading from one fruit to its neighbors — which is better described by a process where individual spoilage events happen at random and can cluster together, rather than by a smooth, continuously-accumulating process. Shape-scaling is the more defensible of the two gamma conventions available, not a claim that this is a physically exact description of how a blueberry actually spoils.

**Why the reference life is pinned this way.** Tying $k$, $\theta$, and $\eta_\text{ref}$ together with one identity, rather than setting them independently, matters because the numbers have to stay consistent with each other. Without that constraint, the implied effective shelf life can end up inconsistent with the intended 14-reference-day commitment, and most of the six real refrigerated shipments used to calibrate this model would arrive largely already spoiled — on the longest of those shipping routes, the model's own spoil-on-arrival probability would reach roughly 90%. A store with nothing to sell isn't a useful simulation of a store: an observation ladder where every scenario agrees "it's already dead" carries no information for any of them to compete over, which defeats the purpose of building the ladder at all. Tying $k\theta\eta_\text{ref} = 1$ removes that inconsistency and preserves a spread of plausible arrival freshness that the model's observation scenarios can actually learn something about.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Q10 temperature factor | $\bar\phi$ | `crates/voi_core/src/physics.rs:38` ([`store_temp_factor`](/api/rust/voi_core/physics/fn.store_temp_factor.html)) |
| Shape-scaled gamma shape for one store day | $k \cdot \bar\phi$ | `crates/voi_core/src/physics.rs:49` (`store_gamma_shape`, private helper) |
| Expected daily decrement | $k\theta\bar\phi$ | `crates/voi_core/src/physics.rs:43` ([`gamma_decrement_for_store`](/api/rust/voi_core/physics/fn.gamma_decrement_for_store.html)) |
| Random daily decrement draw | $\Delta$ | `crates/voi_core/src/physics.rs:55` ([`draw_gamma_decrement`](/api/rust/voi_core/physics/fn.draw_gamma_decrement.html)) |
| Apply decrement, clamp at 0 | $f_\text{next} = \max(f-\Delta, 0)$ | `crates/voi_core/src/physics.rs:230` ([`apply_gamma_decrement`](/api/rust/voi_core/physics/fn.apply_gamma_decrement.html)) |
| Per-unit independent daily freshness loss (production) | — | `crates/voi_core/src/physics.rs:252` ([`apply_gamma_aging_independent`](/api/rust/voi_core/physics/fn.apply_gamma_aging_independent.html)) |
| Gamma shape (fixed) | $k$ | `crates/voi_core/src/params.rs:52` (field), `:77` (default `2.0`) |
| Gamma scale (derived) | $\theta$ | `crates/voi_core/src/params.rs:54` (field), `:89` (`set_reference_life`, derives $\theta = 1/(k\eta_\text{ref})$) |
| Reference shelf life | $\eta_\text{ref}$ | `crates/voi_core/src/params.rs:67` (default `14.0`) |
| Reference temperature | $T_\text{ref}$ | `crates/voi_core/src/params.rs:69` (default `0.0` °C) |
| Studio default store temperature | $T_\text{store}$ | `crates/voi_core/src/params.rs:70` (default `4.0` °C) |
| Q10 doubling factor | $q_{10}$ | `crates/voi_core/src/params.rs:68` (default `2.0`) |
| Reference-life invariant guard test | $k\theta\eta_\text{ref} = 1$ | `crates/voi_core/src/params.rs:63` (`impl Default for ModelParams`, calls `set_reference_life()`) |

## Caveats

- The gamma process is a smooth, continuous idealization. It does not capture discrete loss events — one bruised berry, or mould spreading fruit-to-fruit within a punnet — which would be better modeled as random, clustering events rather than a smooth, continuously-accumulating process.
- Shape-scaling is the model's chosen convention because it's the more defensible of two available options and preserves two structural properties the model relies on (summarizing a trip by $\Lambda$ alone, and getting the same answer regardless of simulation timestep) — it is not presented as a claim of biological exactness.
- The Q10 rule assumes a single multiplicative factor per 10°C across the whole operating range; it does not model freeze injury or chilling-threshold effects, which would be a genuinely different (severity-based, not frequency-based) mechanism that would need a separate term if ever added.
- The reference-life invariant is a calibration choice, not a mathematical coincidence: it ties the gamma distribution's shape and scale together so its expected time-to-zero lines up with the chosen 14-reference-day shelf life. That doesn't mean the gamma distribution and other decay-curve models secretly agree at a deeper mathematical level — it's a deliberate tuning choice, not a natural convergence.

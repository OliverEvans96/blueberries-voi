---
title: Freshness, not age
sources:
  code: [crates/voi_core/src/physics.rs, crates/voi_core/src/rollout.rs, crates/voi_core/src/shipments.rs, src/blueberries_voi/filter/belief.py]
---

# Freshness, not age

Every unit of fruit in this model carries one number for how good it still is: **freshness**, $f$, running from $1$ (pristine) down to $0$ (spoiled). The model doesn't track how many days old a punnet is. "Age" implies one clock ticking the same way for every berry, and that isn't true here — a berry that rode in the warm part of a pallet is worse off than one that rode in the cold part, even though they left the farm on the same day and arrived on the same truck.

## The idea

Freshness behaves like a fuel gauge, not an odometer. An odometer climbs at a fixed rate no matter how you drive; a fuel gauge drains at a rate that depends on conditions — hills, traffic, a heavy foot on the pedal. Freshness starts near full and drains faster under harsher conditions (warmer temperatures), but what's being tracked is remaining quality, not elapsed time.

Two units can spend the same number of calendar days in transit and land with very different freshness if one spent more of that time somewhere warm. "How much warmth this fruit soaked up" is a property of the *journey* — the truck's route and the trailer's temperature log — not something the fruit remembers independently of what happened to it. The model calls that journey property **cumulative thermal exposure**, $\Lambda$ (capital lambda), measured in reference-days. $\Lambda$ gets converted into a freshness *loss*; it is never itself treated as an age painted on the fruit.

## The math

The state variable is freshness $f \in [0, 1]$, with $f = 1$ pristine and $f = 0$ spoiled (fully consumed shelf life). Freshness only ever decreases — see [the gamma-aging page](/store/gamma-aging) for how.

Cumulative thermal exposure $\Lambda$ is the journey's duration adjusted for temperature using Q10 — an Arrhenius-style rule from food science: spoilage roughly multiplies by a factor of Q10 for every 10°C rise in temperature. Concretely, $\Lambda$ is a temperature-weighted integral over calendar time, expressed in *reference-days* (days-equivalent at a fixed reference temperature $T_\text{ref}$):

$$
\Lambda = \int_0^d q_{10}^{\,(T(t) - T_\text{ref})/10}\, dt
$$

where $d$ is the journey's calendar duration in days and $T(t)$ is its temperature path. $\Lambda$ belongs to the corridor (the shipping-route / transit-assumption profile a delivery uses) and the trip, not to any one unit — it exists before any fruit is assigned to it, and every unit riding the same trailer accumulates the same $\Lambda$ (units then diverge in freshness through a per-unit random draw; see the gamma-aging page). Freshness is derived from $\Lambda$, not the other way around, and $\Lambda$ is never itself reported as a unit's "age."

## Why it's modelled this way

Freshness and exposure stay separate because they're different kinds of thing. Freshness is a state that belongs to the fruit and can differ unit-to-unit even within one lot. Exposure is a dose that belongs to the journey, shared by every unit on that journey until a per-unit random draw splits them apart. Keeping the two separate also means $\Lambda$ can summarize everything about a trip's temperature history that matters for freshness in a single number, with nothing lost by summarizing it that way — see the gamma-aging page for why that holds only under the model's chosen scaling convention. Folding exposure back into a per-unit "age" would make it harder for a channel that only sees a calendar date, like a pack-date scan, to reason cleanly about a distribution of possible temperature paths.

A design that keeps an age-in-days number and only converts it to a survival probability at the end would mix together two quantities that need to stay distinct. The same underlying random draw would end up serving as a freshness loss on one code path and as an age-in-days number on another, with no shared convention reconciling them. That means a day of warmth could cost a different amount of freshness depending on which code path touched it.

**Caveat.** This is a naming discipline in the code, not a claim that no code anywhere uses age-like quantities. A couple of legacy research code paths — one in Rust, one in Python — still convert between an age-in-days number and freshness internally. They're kept for backward compatibility with older regression tests and research comparisons. They use a different decay-curve family than the production model, and they sit outside the code path used at runtime. See the table below for exactly where.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Freshness state, mutated in place | $f$ | `crates/voi_core/src/physics.rs:230` ([`apply_gamma_decrement`](/api/rust/voi_core/physics/fn.apply_gamma_decrement.html)) |
| Cumulative thermal exposure along a trip | $\Lambda$ | `crates/voi_core/src/shipments.rs:48` (`arrival_exposure_from_path`, doc: "Cumulative thermal exposure along a temperature path (reference-days)") |
| Legacy age↔freshness conversion helpers, used by a research-only decay-curve variant (Rust) | `age_to_f` / `f_to_age` | `crates/voi_core/src/physics.rs:19`, `:30`; consumers at `crates/voi_core/src/rollout.rs:103` and `crates/voi_core/src/shipments.rs:294` |
| Legacy age-based research helpers, non-production (Python) | `_age_to_f` / `_f_to_age` | `src/blueberries_voi/filter/belief.py:17`, `:21` |

## Caveats

- Freshness $f$ is a modeled quality proxy, not a measured physical quantity — no sensor in this system ever reads $f$ off a real berry (see [No channel ever observes freshness](/ladder/no-channel-observes-freshness)).
- The freshness/exposure split is the convention used by the production model and the UI. The legacy research paths noted above keep age-based language deliberately, scoped as described above.
- Those legacy age-based paths use a different decay-curve family than the production model (see the gamma-aging page). They're kept only so older regression tests stay reproducible, not as an alternate option for production.

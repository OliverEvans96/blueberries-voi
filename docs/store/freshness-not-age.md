---
title: Freshness, not age
sources:
  adr: [0144]
  code: [crates/voi_core/src/physics.rs, crates/voi_core/src/rollout.rs, crates/voi_core/src/shipments.rs, src/blueberries_voi/filter/belief.py]
---

# Freshness, not age

Every unit of fruit in this model carries one number that says how good it still is: **freshness**, written $f$, running from $1$ (pristine) down to $0$ (spoiled). Nothing in the production model tracks how many days old a punnet is. That distinction sounds pedantic until you notice that "age" implies a single clock ticking the same way for every berry, and that isn't true here — a berry that rode in the warm part of a pallet is worse off than one that rode in the cold part, even though they left the farm on the same day and arrive on the same truck.

> **Figure (coming soon):** two units with identical calendar age but different freshness $f$, next to a schematic of $f$ decaying toward 0 while calendar days tick forward at a constant rate — making the "same clock, different odometers" point visually.

## The idea

Think of freshness as a fuel gauge, not an odometer. A car's odometer climbs at a fixed rate no matter how you drive; a fuel gauge drains at a rate that depends on how hard you're driving — hills, traffic, a heavy foot on the pedal. Freshness works like the fuel gauge: it starts near full and drains faster under harsher conditions (warmer temperatures), but the thing being tracked is remaining quality, not elapsed time.

This matters because two units can spend the same number of calendar days in transit and land with very different freshness, if one spent more of that time somewhere warm. Conversely, "how much warmth has this fruit soaked up" is a property of the *journey* — the truck's route and the trailer's temperature log — not a number the fruit itself remembers independently of what happened to it. The model calls that journey property **cumulative thermal exposure**, $\Lambda$ (capital lambda), measured in reference-days. $\Lambda$ is an input that gets converted into a freshness *loss*; it is never itself treated as an age painted on the fruit.

## The math

The state variable is freshness $f \in [0, 1]$, with $f = 1$ pristine and $f = 0$ spoiled (fully consumed shelf life). Freshness only ever decreases — see [the gamma-aging page](/store/gamma-aging) for exactly how.

Cumulative thermal exposure $\Lambda$ is the Q10-warped duration of a journey — a temperature-weighted integral over calendar time, expressed in *reference-days* (days-equivalent at a fixed reference temperature $T_\text{ref}$):

$$
\Lambda = \int_0^d q_{10}^{\,(T(t) - T_\text{ref})/10}\, dt
$$

where $d$ is the journey's calendar duration in days and $T(t)$ is its temperature path. $\Lambda$ belongs to the *corridor and the trip* — it exists before any fruit is assigned to it, and every unit riding the same trailer accumulates the same $\Lambda$ (units then diverge in freshness through a per-unit random draw; see the gamma-aging page). Freshness is derived from $\Lambda$, not the other way around, and $\Lambda$ is never itself reported as a unit's "age."

## Why it's modelled this way

ADR 0144 retires "effective age" from the UI and the live implementation because the age framing conflated two different things: a state that belongs to the fruit (freshness, which can differ unit-to-unit even within one lot) and a dose that belongs to the journey (exposure, shared by every unit on that journey until the per-unit gamma draw splits them apart). Keeping the two separate is also what lets $\Lambda$ work as a sufficient statistic for a trip's temperature history — see the gamma-aging page for why that only holds under the model's chosen scaling convention. Blurring exposure back into a per-unit "age" would make it harder for a rung that only ever sees a calendar date (like a pack-date scan) to reason cleanly about a distribution of possible temperature paths.

The rejected alternative — keeping an age-in-days state variable and converting it to a survival probability only at the very end — is essentially the pre-remodel design ADR 0144 describes as broken: the same underlying gamma draw was being used as a freshness loss on one code path and as an age-in-days on another, with no shared convention reconciling them, so a day of warmth cost a different amount of freshness depending on which branch of the code happened to touch it.

**Caveat.** This is a naming and API discipline, not a claim that no code anywhere still uses age-like quantities. Two legacy `age_to_f` / `f_to_age` conversion helpers still exist in `crates/voi_core/src/physics.rs`, used by the legacy Weibull-survival research path in `crates/voi_core/src/rollout.rs` (terminal salvage under an older survival-curve convention) and by `crates/voi_core/src/shipments.rs`'s `truth_birth_from_trace`, which is explicitly documented in-source as "ground-truth birth freshness ... under legacy Weibull mapping." These are retained under their existing names purely so old goldens and research comparisons stay reproducible; they sit off the production hot path. Separately, the Python research code in `src/blueberries_voi/filter/` and `src/blueberries_voi/sim/` intentionally keeps the older age-based vocabulary (`age_at_receipt`, `_age_to_f`, `_f_to_age`) as an allowlisted research path — this is explicitly not the production model. A repo-wide grep guard enforces that these retired terms don't leak anywhere else.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Freshness state, mutated in place | $f$ | `crates/voi_core/src/physics.rs:223` ([`apply_gamma_decrement`](/api/rust/voi_core/physics/fn.apply_gamma_decrement.html)) |
| Cumulative thermal exposure along a trace | $\Lambda$ | `crates/voi_core/src/shipments.rs:21` (`arrival_exposure_from_path`, doc: "Cumulative thermal exposure along a temperature path (reference-days)") |
| Legacy age↔freshness map (research path only) | `age_to_f` / `f_to_age` | `crates/voi_core/src/physics.rs:15`, `:23` |
| Legacy consumer — Weibull salvage | — | `crates/voi_core/src/rollout.rs:90` (`f_to_age` in `terminal_salvage_unit_state`) |
| Legacy consumer — ground-truth birth freshness | — | `crates/voi_core/src/shipments.rs:107` (`truth_birth_from_trace`, doc: "under legacy Weibull mapping") |
| Python research-path age helpers (allowlisted, non-production) | `_age_to_f` / `_f_to_age` | `src/blueberries_voi/filter/belief.py:17`, `:21` |
| Terminology grep guard (bans "effective age" / `age_at_receipt` / `age_marginal` outside the allowlist) | — | `crates/voi_core/tests/t150_phase1_terminology.rs:102` (`ac1_3_effective_age_grep_guard_with_allowlist`) |

## Caveats

- Freshness $f$ is a modeled quality proxy, not a measured physical quantity — no sensor in this system ever reads $f$ off a real berry (see [No channel ever observes freshness](/ladder/no-channel-observes-freshness)).
- The freshness/exposure split is a live-code and UI convention as of ADR 0144; historical ADRs, `.team/` records, and notebooks predating the remodel keep the older "age" language as a record of what was decided at the time, and are deliberately not rewritten to match.
- The legacy Weibull `age_to_f`/`f_to_age` path uses a different survival-curve family than the production gamma-decrement path (see the gamma-aging page); it is kept only so older goldens stay reproducible, not as an alternate production option.

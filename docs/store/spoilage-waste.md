---
title: Spoilage and waste
sources:
  adr: [0143]
  code: [crates/voi_core/src/day_step.rs, crates/voi_core/src/physics.rs]
---

# Spoilage and waste

A unit becomes waste the moment its freshness hits zero — no separate coin flip, no shared store-wide event, just one unit's own daily freshness draw running out. This page covers how that's tracked in the simulator: which unit spoiled, when, and in which lot, all of which feed the waste counts a store (and its filter) actually gets to see.

> **Figure (coming soon):** a small multiples plot of freshness trajectories for the ~15 units in one lot over a couple of weeks, each aging independently, showing them crossing zero on different days rather than all together.

## The idea

Every alive unit loses a random amount of freshness each day (see [how fruit ages](/store/gamma-aging) for the full mechanism), and that random amount is drawn **independently for every unit** — not once for the whole store, and not once per lot. A lot that arrives with fifteen units all at freshness $0.85$ doesn't stay a tidy, uniform block: over the following days, some units in that lot get unlucky draws and lose freshness fast, others get lucky and barely change, and the lot spreads out. A unit is marked **spoiled** — removed from what can be sold, counted as waste — the instant its own freshness crosses zero, whatever day that happens to be for that particular unit.

The practical upshot is that a single delivery's waste doesn't arrive as one lump. Fifteen units from the same truck can spoil across a span of several days rather than all going bad at once, because "the same truck" only means they started at similar freshness — after that, each unit's fate is its own random draw.

## The math

For each alive unit $i$ (freshness $f_i > 0$) on a given day, an independent decrement is drawn:

$$
\Delta_i \sim \mathrm{Gamma}(k \cdot \bar\phi,\ \theta), \qquad f_i \leftarrow \max(f_i - \Delta_i,\ 0)
$$

using the same gamma law described on the aging page — $k$ the shape parameter, $\theta$ the scale parameter, $\bar\phi$ the day's Q10 temperature factor — except that where the daily aging step draws one $\Delta$, here every unit gets its **own** $\Delta_i$, drawn separately.

A unit is recorded as spoiled on the first day its post-decrement freshness reaches zero: comparing freshness before and after that day's decrement, unit $i$ is waste if $f_i^{\text{before}} > 0$ and $f_i^{\text{after}} \le 0$. Per lot $\ell$, the day's waste count is

$$
\text{waste\_by}[\ell] = \#\{\, i \in \ell : f_i^{\text{before}} > 0 \text{ and } f_i^{\text{after}} \le 0 \,\}
$$

and every spoiled unit's identity, its freshness at the moment it spoiled, and a `Spoiled` cause code are recorded individually — the same per-unit event log used to record a sale (see [one day, in order](/store/one-day-in-order)).

## Why it's modelled this way

An earlier design (ADR 0137, since superseded) drew **one shared decrement** for every live unit in the store on a given day. That kept every unit in a lot moving in lockstep — freshness-homogeneous within a lot — which had a specific downside: because a lot's units could only ever spoil together, observing how many units in a lot spoiled on a given day could tell the filter that its *ordering* of freshness across lots was wrong (a contrast check), but it could never sharpen the filter's belief about the freshness *level* itself, because there was nothing for individual units within a lot to disagree about.

Diagnostic work (an earlier notebook investigating GSIN vs. UPC-pooled observation channels) found this was a real structural ceiling: information about the store's freshness level was coming from pack-date and delivery-history channels, not from lot-resolved spoilage counts, precisely because the shared-decrement model gave spoilage nothing to say about level. ADR 0143's decision — independent per-unit decrements — was adopted to test the hypothesis that letting units diverge *before* spoiling would unlock lot-resolved waste as a genuinely level-informative channel, scored with an exact Poisson-binomial likelihood over each unit's individual spoil probability rather than a single shared-event calculation. (How the filter actually uses that likelihood to update its beliefs is a separate topic, covered on the inference pages — this page only covers how spoilage happens in the ground truth.)

**Honest caveat.** Independent draws are still *identically* distributed — every unit in the same store, same day, draws from the same Gamma law; the model doesn't give units in, say, a colder part of a pallet a systematically different decrement day-to-day (any pallet-position effect is baked into a unit's *birth* freshness once, via the arrival model's within-pallet multiplier, not re-applied on every subsequent shelf day). And independence is a modeling assumption, not a claim about physical mechanism: real spoilage can be contagious — one moldy berry spreading to its neighbors within a punnet, or a whole case affected by one bad handling event — which independent per-unit draws don't represent at all.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Independent per-unit daily decrement (production ground truth) | $\Delta_i$ | `crates/voi_core/src/physics.rs:245` ([`apply_gamma_aging_independent`](/api/rust/voi_core/physics/fn.apply_gamma_aging_independent.html)) |
| Apply one decrement, clamp at 0 | $f \leftarrow \max(f-\Delta, 0)$ | `crates/voi_core/src/physics.rs:223` ([`apply_gamma_decrement`](/api/rust/voi_core/physics/fn.apply_gamma_decrement.html)) |
| Spoil cause code on a per-unit exit record | `UnitExitCause::Spoiled` | `crates/voi_core/src/day_step.rs:34` |
| Detect newly-spoiled units (before/after comparison) | `waste_by[ℓ]` | `crates/voi_core/src/day_step.rs:98` (`count_spoil_by_lot`) |
| Per-unit spoiled-exit records (unit id, freshness at spoil, cause) | — | `crates/voi_core/src/day_step.rs:114` (`spoil_unit_exits`) |
| Deterministic shared-decrement path (tests only) | — | `crates/voi_core/src/day_step.rs:89` (`apply_gamma_step`, `gamma_decrement: Some(d)` branch) |
| Precomputed spoil-probability table for the current parameters | $P(\delta \ge f)$ | `crates/voi_core/src/physics.rs:340` ([`GammaDecrementTable::spoil_prob`](/api/rust/voi_core/physics/struct.GammaDecrementTable.html#method.spoil_prob)) |

## Caveats

- Spoilage is checked once per simulated day, at day granularity — the model doesn't resolve *when within* a day a unit crossed zero, only that it had by the day's end.
- Decrements are independent draws from one shared Gamma law, not correlated by physical proximity within a lot or pallet; there is no contagion or neighbor-effect mechanism.
- The deterministic shared-decrement input (`gamma_decrement: Some(d)`) exists only to make tests reproducible; it is not how the production truth path ages inventory.
- This page describes how spoilage happens in the simulated store, not how a filter that only observes aggregate waste counts infers anything from it — that scoring logic lives on the inference side of the site.

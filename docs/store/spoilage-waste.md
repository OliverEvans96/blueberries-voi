---
title: Spoilage and waste
sources:
  code: [crates/voi_core/src/day_step.rs, crates/voi_core/src/physics.rs]
---

# Spoilage and waste

A unit becomes waste the moment its freshness hits zero. There's no separate coin flip and no shared, store-wide event — just one unit's own daily freshness draw running out. This page covers how that gets tracked in the simulator: which unit spoiled, when, and in which lot. Those details feed the waste counts that a store (and its belief-tracking filter) actually gets to see.

## The idea

Every unit on the shelf loses a random amount of freshness each day (see [how freshness decays](/store/gamma-aging) for the full mechanism). That random amount is drawn **independently for every unit** — not once for the whole store, and not once per lot. Say a lot arrives with fifteen units, all at freshness $0.85$. It doesn't stay a tidy, uniform block. Over the following days, some units get unlucky draws and lose freshness fast, others get lucky and barely change, and the lot spreads out. A unit is marked **spoiled** — removed from what can be sold, counted as waste — the instant its own freshness crosses zero, whatever day that happens to be for that particular unit.

The practical upshot: a single delivery's waste doesn't arrive as one lump. Fifteen units from the same truck can spoil across a span of several days rather than all going bad at once. "The same truck" only means they started at similar freshness — after that, each unit's fate is its own random draw.

## The math

For each alive unit $i$ (freshness $f_i > 0$) on a given day, an independent decrement is drawn:

$$
\Delta_i \sim \mathrm{Gamma}(k \cdot \bar\phi,\ \theta), \qquad f_i \leftarrow \max(f_i - \Delta_i,\ 0)
$$

This uses the same gamma law described on the aging page — $k$ is the shape parameter, $\theta$ is the scale parameter, and $\bar\phi$ is the day's Q10 temperature factor (Q10 is an Arrhenius-style rule from food science — spoilage roughly multiplies by Q10 for every 10°C rise in temperature). The only difference from the daily aging step is that instead of drawing one shared $\Delta$, here every unit gets its **own** $\Delta_i$, drawn separately.

A unit is recorded as spoiled on the first day its freshness reaches zero after that day's decrement. Comparing freshness before and after the decrement, unit $i$ is waste if $f_i^{\text{before}} > 0$ and $f_i^{\text{after}} \le 0$. Per lot $\ell$, the day's waste count is

$$
\text{waste\_by}[\ell] = \#\{\, i \in \ell : f_i^{\text{before}} > 0 \text{ and } f_i^{\text{after}} \le 0 \,\}
$$

Every spoiled unit's identity, its freshness at the moment it spoiled, and a "spoiled" cause code are recorded individually — the same per-unit event log used to record a sale (see [one day, in order](/store/one-day-in-order)).

## Why it's modelled this way

Drawing an independent decrement for every unit — rather than one shared decrement for the whole store or lot — lets units within a lot diverge before any of them spoil. That divergence is what makes lot-by-lot waste counts informative about the freshness *level* within a lot, not just about which lot is fresher than which.

Here's why that matters. If every unit in a lot moved in lockstep, a filter could still learn something from waste counts: if one lot spoils faster than another, that tells the filter it had the lots' relative freshness backwards. But it could never learn anything sharper than that ranking, because there'd be nothing for individual units within a lot to disagree about — they'd all spoil on the same day. Letting units diverge before spoiling unlocks something more useful: lot-resolved waste becomes a channel that can sharpen the filter's belief about the actual freshness level, not just its ranking across lots.

To take advantage of that, the day's waste count for a lot is scored with a calculation that accounts for every unit's own, slightly different chance of having spoiled — rather than treating the whole lot's spoilage as one shared coin flip. How the filter actually uses that calculation to update its beliefs is a separate topic, covered on the inference pages. This page only covers how spoilage happens in the simulator's actual, true state — as opposed to what the filter believes — what the rest of the site calls "ground truth."

**Honest caveat.** Independent draws are still *identically* distributed: every unit in the same store, on the same day, draws from the same gamma law. The model doesn't give units in, say, a colder part of a pallet a systematically different decrement day-to-day. Any pallet-position effect is baked into a unit's starting freshness once, when it arrives — via the arrival model's inter-lot position noise, the fact that each lot's units don't all arrive at exactly the same freshness — and it isn't reapplied on every later shelf day. Independence is also a modeling assumption, not a claim about physical mechanism — real spoilage can be contagious. One moldy berry can spread to its neighbors within a punnet, or a whole case can be affected by one bad handling event. Independent per-unit draws don't represent that at all.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Independent per-unit daily decrement (production ground truth) | $\Delta_i$ | `crates/voi_core/src/physics.rs:252` ([`apply_gamma_aging_independent`](/api/rust/voi_core/physics/fn.apply_gamma_aging_independent.html)) |
| Apply one decrement, clamp at 0 | $f \leftarrow \max(f-\Delta, 0)$ | `crates/voi_core/src/physics.rs:230` ([`apply_gamma_decrement`](/api/rust/voi_core/physics/fn.apply_gamma_decrement.html)) |
| Spoil cause code on a per-unit exit record | `UnitExitCause::Spoiled` | `crates/voi_core/src/day_step.rs:40` |
| Detect newly-spoiled units (before/after comparison) | `waste_by[ℓ]` | `crates/voi_core/src/day_step.rs:120` (`count_spoil_by_lot`) |
| Per-unit spoiled-exit records (unit id, freshness at spoil, cause) | — | `crates/voi_core/src/day_step.rs:138` (`spoil_unit_exits`) |
| Deterministic shared-decrement path (tests only) | — | `crates/voi_core/src/day_step.rs:103` (`apply_gamma_step`, `gamma_decrement: Some(d)` branch) |
| Precomputed spoil-probability table for the current parameters | $P(\delta \ge f)$ | `crates/voi_core/src/physics.rs:356` ([`GammaDecrementTable::spoil_prob`](/api/rust/voi_core/physics/struct.GammaDecrementTable.html#method.spoil_prob)) |

## Caveats

- Spoilage is checked once per simulated day, at day granularity — the model doesn't resolve *when within* a day a unit crossed zero, only that it had by the day's end.
- Decrements are independent draws from one shared gamma law, not correlated by physical proximity within a lot or pallet. There is no contagion or neighbor-effect mechanism.
- A deterministic, shared-decrement input exists only to make tests reproducible; it is not how the production truth path ages inventory.
- This page describes how spoilage happens in the simulated store, not how a filter that only observes aggregate waste counts infers anything from it — that scoring logic lives on the inference side of the site.

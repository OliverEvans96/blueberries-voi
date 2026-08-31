---
title: The store in five minutes
sources:
  code: [crates/voi_core/src/day_step.rs, crates/voi_core/src/physics.rs]
---

# The store in five minutes

Everything on this site is built from one repeating unit: a single simulated day in
a single store. Once you know what happens in one day, the rest of the model — the
physics, the filter, the ordering rule, the VOI number — is just that, repeated,
with uncertainty layered on top. This page walks through one day in plain words, in
the order the code runs it. No equations yet; those come once the pieces have
names.

## The idea

Picture the shelf at the start of a day as a row of punnets, each with a freshness
value between 1 (just picked) and 0 (dead). Four things happen to that shelf, in
this order, every day of the simulation:

**1. Every unit on the shelf ages a little.** Each punnet loses a small, random
amount of freshness, drawn independently per punnet from a gamma process, faster on
average when the store is warmer. Two punnets that started the day identical can
end it slightly different.

**2. Any unit whose freshness has hit zero is marked spoiled.** A unit can age all
the way to 0 and become waste. There's no separate spoilage roll — a unit spoils
exactly when its freshness reaches zero during step 1, and it's removed from the
sellable pool immediately.

**3. Customers buy some units.** Demand for the day is drawn, and that many units
are sold — but not strictly oldest-first, and not uniformly at random either.
Shoppers prefer fresher punnets, but only probabilistically: a freshness-weighted
random draw picks which units leave the shelf, so a middling punnet can still get
picked ahead of a slightly fresher one now and then.

**4. Today's delivery arrives and joins the shelf, after selling is done.** A new
lot of units shows up, each with its own starting freshness set by a cold-chain
model (trip duration, truck temperature, position in the pallet — covered on a
later page). Delivery happens after sales on purpose: today's truck cannot be sold
to today's first customers, only tomorrow's.

## Why it's modelled this way

The order matters more than it looks. Near the fragile end of the parameter
range — where units are close to spoiling — whether spoilage is checked before or
after sales, and whether delivery lands before or after sales, shifts how much
gets sold versus wasted. So the order is fixed: age first, then resolve what's
sellable, then sell, then deliver last. The simulator and the belief-tracking
filter use this exact same order — if they didn't, the filter would be modeling a
different store than the one actually running.

Spoilage is folded directly into the aging draw: a unit spoils the moment its
continuous freshness loss reaches zero, before sales are drawn, not after. There is
no separate spoilage check applied afterward.

## In the code

| Step | What happens | File : line |
| --- | --- | --- |
| 1. Aging | Each alive unit gets an independent random freshness loss, faster when warmer | `crates/voi_core/src/day_step.rs:269` (`apply_gamma_step`), `crates/voi_core/src/physics.rs:252` ([`apply_gamma_aging_independent`](/api/rust/voi_core/physics/fn.apply_gamma_aging_independent.html)) |
| 2. Spoilage | Units whose freshness fell to zero are counted and marked as waste exits | `crates/voi_core/src/day_step.rs:275` (`count_spoil_by_lot`) |
| 3. Sales | Demand is filled by a freshness-weighted random draw over alive units | `crates/voi_core/src/day_step.rs:283` (`pick_units_f`), `crates/voi_core/src/physics.rs:380` ([`picking_weights_f`](/api/rust/voi_core/physics/fn.picking_weights_f.html)) |
| 4. Delivery | A new lot is appended to the shelf, each unit's freshness set by the arrival model | `crates/voi_core/src/day_step.rs:287` (`if input.deliver`) |
| Whole day | Runs steps 1–4 in this fixed order | `crates/voi_core/src/day_step.rs:254` ([`unit_day_step_with_birth`](/api/rust/voi_core/day_step/fn.unit_day_step_with_birth.html)) |

## Caveats

This page describes the mechanics, not the randomness driving them — how big the
aging loss typically is, how "prefer fresher" is weighted, and how a delivery's
starting freshness is chosen are each covered on their own pages with the numbers
attached. It also doesn't cover what the store gets to see: a unit spoiling or
selling doesn't mean anyone running the store observed it happen. What's
observable depends on the observation scenario, covered under "What the store can
see."

Every day, repeated, is the whole simulation; the rest of this site explains each
piece precisely.

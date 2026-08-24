---
title: The store in five minutes
sources:
  adr: [34, 143, 144]
  code: [crates/voi_core/src/day_step.rs, crates/voi_core/src/physics.rs]
---

# The store in five minutes

Everything on this site is built out of one repeating unit: a single simulated day
in a single store. Get comfortable with what happens over the course of one day and
the rest of the model — the physics, the filter, the ordering rule, the VOI
number — is just "that, over and over, with uncertainty layered on top." This page
walks through one day in plain words, in the exact order the code runs it. No
equations here; those come later, once the pieces have names.

> **Figure (coming soon):** a horizontal timeline of one simulated day showing four
> panels in order — shelf ages, spoiled units drop out, customers buy, the new
> delivery joins the shelf — with a small blueberry icon fading from full color to
> grey as its freshness falls.

## The idea

Picture the shelf at the start of a day as a row of punnets, each with its own
freshness value between 1 (just picked) and 0 (dead). Four things happen to that
shelf, in this order, every single day of the simulation:

**1. Every unit on the shelf ages a little.** Overnight and through the day, each
punnet loses a small, random amount of freshness. The loss isn't the same for every
unit — it's drawn independently per punnet from a random process (a *gamma*
process), and it's drawn faster, on average, when the store is warmer. Two punnets
that started the day identical can end it slightly different.

**2. Any unit whose freshness has hit zero is marked spoiled.** Aging isn't capped
at "gets old and stays sellable" — a unit can age all the way to 0 and become
waste. There's no separate "spoilage roll" after the fact: a unit spoils exactly
when its freshness reaches zero during step 1, and it's swept out of the sellable
pool immediately.

**3. Customers buy some units.** Demand for the day is drawn, and that many units
are sold — but not strictly the oldest first, and not uniformly at random either.
Shoppers *prefer* fresher punnets, but only probabilistically: a freshness-weighted
random draw picks which units leave the shelf, so a middling punnet can still get
picked ahead of a slightly fresher one now and then, the way real shoppers behave
at the produce case.

**4. Today's delivery arrives and joins the shelf — after the selling is done.**
A new lot of units shows up, each with its own starting freshness set by a
cold-chain model (how long the trip took, how warm the truck ran, where in the
pallet the unit sat — covered on a later page). Delivery happens *after* sales on
purpose: today's truck cannot be sold to today's first customers, only tomorrow's.

## Why it's modelled this way

The order matters more than it looks. At the fragile end of the parameter range —
where units are close to spoiling — whether spoilage is checked before or after
sales, and whether delivery lands before or after sales, systematically shifts how
much gets sold versus wasted. The project's own design record settles this
explicitly: age first, then resolve what's sellable, then sell, then deliver last,
and the simulator and the belief-tracking filter are required to agree on the exact
same order — if they didn't, the filter would be quietly modeling a different store
than the one actually running.

One thing worth being honest about: the *mechanism* for step 2 changed partway
through the project. Earlier notes describe spoilage as a separate random check
applied to whichever units survive the day's sales. The current model folds
spoilage directly into the aging draw instead — a unit spoils the moment its
continuous freshness loss reaches zero, before sales are drawn, not after. Both
versions keep "age first, deliver last," but if you go looking at older design
notes, don't be surprised to see a different, no-longer-current description of
exactly where the spoilage check sits relative to the sale.

## In the code

| Step | What happens | File : line |
| --- | --- | --- |
| 1. Aging | Each alive unit gets an independent random freshness loss, faster when warmer | `crates/voi_core/src/day_step.rs:232` (`apply_gamma_step`), `crates/voi_core/src/physics.rs:245` (`apply_gamma_aging_independent`) |
| 2. Spoilage | Units whose freshness fell to zero are counted and marked as waste exits | `crates/voi_core/src/day_step.rs:238` (`count_spoil_by_lot`) |
| 3. Sales | Demand is filled by a freshness-weighted random draw over alive units | `crates/voi_core/src/day_step.rs:246` (`pick_units_f`), `crates/voi_core/src/physics.rs:360` (`picking_weights_f`) |
| 4. Delivery | A new lot is appended to the shelf, each unit's freshness set by the arrival model | `crates/voi_core/src/day_step.rs:250` (`if input.deliver`) |
| Whole day | Runs steps 1–4 in this fixed order | `crates/voi_core/src/day_step.rs:217` (`unit_day_step_with_birth`) |

## Caveats

This page describes the mechanics, not the randomness driving them — how big the
aging loss typically is, how "prefer fresher" is actually weighted, and how a
delivery's starting freshness is chosen are each covered on their own pages with
the numbers attached. It also doesn't cover what the *store* gets to see about any
of this — that a unit spoiled or sold doesn't mean anyone running the store
observed it happen; what's observable depends on the knowledge rung, covered under
"What the store can see."

Every day, repeated, is the whole simulation; the rest of this site explains each
piece precisely.

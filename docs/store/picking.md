---
title: Who buys which punnet
sources:
  code: [crates/voi_core/src/physics.rs, crates/voi_core/src/day_step.rs, crates/voi_core/src/params.rs]
---

# Who buys which punnet

When a customer buys blueberries, the model has to decide *which physical unit* on the shelf they took — the punnet from Monday's delivery, or the one from Wednesday's? This page is about that choice. It is not first-in-first-out, and getting that right matters: it determines how long an old, unlucky punnet can linger on the shelf before it either sells or spoils, which is exactly the kind of thing a store's freshness beliefs are trying to track.

## The idea

Picture the shelf as a small lottery, redrawn one ticket at a time. Every unit still alive (freshness $f > 0$) gets a ticket; fresher units get proportionally more tickets, so they're more *likely* to be drawn, but every alive unit — however tired — always holds at least one ticket. A customer walks up, the model draws one ticket, that unit is sold, and its tickets leave the drum. Then the next customer's draw is run on whatever's left. This repeats once per sale, so the odds shift after every single purchase as the mix of what's still on the shelf changes.

This is deliberately **not FIFO** (first-in-first-out). Nobody reaches to the back of the display for the oldest punnet — that's not how self-service produce shopping works. FIFO is a *store*-side lever (rotation, facing forward stock), not a customer preference, and it isn't modeled as one here. The only place "first in" matters at all is bookkeeping: once a lot's units are all gone (sold or spoiled), that lot drops off the belief wire in oldest-first order. That's a statement about which lots the store still has open records for, not about which unit a shopper reaches for. A consequence worth sitting with: under this fresh-biased lottery, an old unit can survive on the shelf for a surprisingly long time if it simply never gets drawn — it isn't waiting in some queue position that guarantees it'll be sold next.

## The math

For a given sale, let $f_i$ be the current freshness of alive unit $i$ (only units with $f_i > 0$ are eligible). The picking weight is

$$
w_i = \frac{\max(f_i, 0)^\sigma}{\sum_j \max(f_j, 0)^\sigma}
$$

where $\sigma$ (sigma) is the **picking-weight exponent**, a fixed model parameter (default $\sigma = 0.5$), and the sum runs over every currently-alive unit. A larger $\sigma$ pushes weight more aggressively toward the freshest units; $\sigma = 0$ (or the model's `uniform_picking` flag) collapses this to $w_i = 1/n$ for all $n$ alive units — pure random picking, no freshness preference at all.

One day's sales are not one draw from this distribution — they're a sequence of draws. If demand for the day is $\text{to\_sell} = \min(\text{demand}, \, \#\{i : f_i > 0\})$ units, the model draws one unit at a time: compute $w_i$ over the *currently* alive set, sample one unit proportional to those weights, remove it, and repeat until `to_sell` units have been picked. This is sampling **without replacement**, with weights **recomputed after every pick** — not a single multinomial draw against fixed weights, and not Bernoulli sampling with replacement.

## Why it's modelled this way

The picking kernel's form is deliberate, and the FIFO point is explicit: in self-service produce, the issuing order isn't something the store controls. Almost every textbook perishable-inventory paper assumes the store can choose to sell its oldest stock first, and this model deliberately does not make that assumption. A two-parameter logistic-in-age kernel would be more flexible, but untethered from the physics; a softmax-with-temperature form is equivalent to the chosen kernel up to reparameterization. A uniform/random kernel is kept as a baseline switch (`uniform_picking`) rather than promoted to the model.

The numeric value, $\sigma = 0.5$, is used as a single "moderately fresh-biased" base case, plus one uniform-picking sensitivity cell. Using one fixed $\sigma$ with no sensitivity check at all would leave the result resting on an unjustified scalar; promoting $\sigma$ to a third sweep axis alongside the model's main experimental axes would reopen a settled scope decision.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Picking weights over alive units | $w_i$ | `crates/voi_core/src/physics.rs:380` ([`picking_weights_f`](/api/rust/voi_core/physics/fn.picking_weights_f.html)) |
| Picking-weight exponent (field, default `0.5`) | $\sigma$ | `crates/voi_core/src/params.rs:38` (field), `:71` (default) |
| Uniform-picking override flag | — | `crates/voi_core/src/params.rs:47` (field), `:75` (default `false`) |
| Sequential without-replacement sales loop (recomputes weights each pick) | — | `crates/voi_core/src/day_step.rs:166` (`pick_units_f`) |
| Units eligible to sell = alive count | $\#\{f_i > 0\}$ | `crates/voi_core/src/day_step.rs:176` (`to_sell = demand.min(...)`) |
| Lots leave the belief wire oldest-first (bookkeeping, not a picking rule) | — | `crates/voi_core/src/belief_flat.rs:29` (doc comment) |

## Caveats

- This is a lottery re-drawn per unit, not a single multinomial shot: the "Wallenius-style" sequential re-weighting means the *effective* selection probabilities for a whole day's sales are not simply the single-draw weights above — they shift as the shelf empties.
- Freshness is the only thing that biases picking; the model doesn't represent shelf position, facing, package appearance, price markdowns, or any other real-world cue a shopper might actually use.
- FIFO governs lot bookkeeping (when an emptied lot's record is retired), never which unit within the currently-alive stock gets sold — conflating the two would be a mistake.
- $\sigma$ is a single fixed number for the whole store and every observation scenario; the model does not fit or vary it per experiment condition beyond the one uniform-picking sensitivity cell.

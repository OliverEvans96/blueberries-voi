# T-150 arrival remodel — current behaviour

This note is about **what the store does now**, not how the ticket was built.

## What someone using the studio sees

Deliveries no longer arrive with one known freshness. Each pack’s freshness at the
door is drawn from a corridor-specific story: a minimum transit time, extra delay,
a typical reefer temperature with some spread, and a little extra scatter from
where the pack sat in the load. The filter only uses what that knowledge rung is
allowed to see — books-only knows the corridor mix; a pack date pins duration;
a temperature trace pins cumulative heat.

Shelf life is **one** number: two weeks at the reference temperature. Daily aging
and transit aging share that number. The old pair of disagreeing lives is gone.

Arrival freshness is an **upper bound**. Heat between harvest and the refrigerated
leg is out of scope, by choice. The six Abdella shipments were used to **anchor
assumed families** (typical duration and temperature). They do not prove those
families, and they are not a fit.

## Decisions that stay

- Duration, not a secret temperature swing, is most of the uncertainty in
  cumulative heat. That is why a pack date helps a lot and a full temperature
  trace helps less.
- No channel observes freshness itself. A date is a duration; a trace is a heat
  integral. The filter never peeks at true `f`.
- Studio corridors “short haul” and “long haul” are illustrations so the product
  chip can change physics. Only the default mixed corridor is tied to the six
  shipments’ moments.

## What the accuracy numbers say (current run)

On a 30-day shared-order replay, three seeds, damped base-stock (no rollout):

| Knowledge | Mean |belief − truth| on shelf freshness |
| --- | --- |
| Books only (P0) | 0.109 |
| Waste totals (P1) | 0.114 |
| Pack date (F2a / F2) | 0.034 / 0.032 |
| Temperature trace (F3) | 0.017 |

Pack date is the large step (about 3×). The temperature trace is a smaller
follow-on (about half the remaining error), concentrated in leftover duration
rounding and path heat — not a second pack-date-sized jump.

Waste totals are not automatically more accurate than books-only on this path.
Lot-code rungs without a pack date compile to the same observation bundle as
each other.

Closed-loop profit under the same damped policy still moves more with the random
seed than with the observation rung. Sharper freshness beliefs are real; they
have not yet shown up as reliable extra dollars at this budget.

## What this note is not

It is not a claim that Abdella’s six loads validate the generative family. It is
not a 17-minute GSIN diagnostic refresh — that file still describes the previous
spoilage-likelihood epoch. The arrival-ladder evidence for this remodel is the
filter-accuracy replay above.

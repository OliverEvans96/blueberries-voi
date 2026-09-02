---
title: Limitations
sources:
  code:
    - crates/voi_core/src/arrival_wire.rs
    - crates/voi_core/src/session.rs
    - data/abdella/arrival_model.json
    - web/src/controls.ts
---

# Limitations

Every other page on this site describes what the model does. This one gathers what it
deliberately doesn't do, or can't yet do, in one place instead of scattering it as
footnotes. None of these are hidden defects. Each is a considered scope decision or a
known gap, and most already have a caveat on the page where they're most relevant. This
page exists so you don't have to hunt across the whole site to get the full list at once.

## The idea

Read this as a checklist for reading any result on this site with the right amount of
skepticism — not as a reason to distrust the model wholesale. Some of these are hard scope
boundaries chosen on purpose: the model only covers the refrigerated leg of a shipment.
Some are honest consequences of a small dataset: just six real shipments. Some are known
display or wiring gaps that just haven't been closed yet: a studio control that changes
the simulation but not the chart next to it. And one is a simplification common to almost
every spoilage model of this kind: a smooth, continuous decay standing in for spoilage
that's really a bit more sudden and patchy than that.

## The math

This page is a synthesis, not a new derivation. The quantitative claims below — the 98.4%
duration share, the illustrative cost figures, the six-shipment sample size — each come
from, and are derived in detail on, the page that owns them. See the cross-links in each
item below.

## Why it's modelled this way

This isn't one modeling choice — each item below is its own decision, made for its own
reasons, described in full on its own page. What's consistent across all of them is a
project-wide preference: state a limitation plainly and move on, rather than quietly
shipping a model that looks more capable than the underlying evidence supports.

## In the code

| Limitation | Where it's enforced / visible | File:line |
| --- | --- | --- |
| Refrigerated-leg-only scope (arrival freshness is an upper bound) | Arrival window excludes field heat | `data/abdella/arrival_model.json` (`provenance.window`); see [Cold-chain arrival model](/store/cold-chain-arrival) |
| Arrival families assumed, not fitted, on n=6 shipments | `provenance.notes`: six strawberry logger shipments, not fitted by Maximum Likelihood Estimation | `data/abdella/arrival_model.json` |
| Studio corridor temperature-bias control not applied to the displayed arrival chart | Bias control accepted but unused in the chart-generating path, though it is applied to the simulated truth path (`transit_temp_bias_c`) | `crates/voi_core/src/arrival_wire.rs:69-81` (applied to truth path at `crates/voi_core/src/session.rs:450`; a code comment on `arrival_summary_wire` notes the same bias is accepted for consistency but deliberately not applied there) |
| Studio corridor selector exposes only the default blend, not its individual corridors | Only chip is the "Abdella mix" default (`abdella_mix`), a blend of a short-haul corridor (anchored to shipment S2) and a long-haul corridor (anchored to shipments S1, S3–S6); the pooled and individual corridors (`abdella_all`, `short_haul`, `long_haul`) aren't separately selectable | `data/abdella/arrival_model.json` (`corridors`, `corridor_mixtures.abdella_mix`); studio chip at `web/src/controls.ts:490-491` |

## Caveats

The items below are the limitations themselves — each is a caveat by nature, so this
section *is* the list rather than a summary of it.

1. **Refrigerated-leg-only scope.** The model covers only the segment from the first
   below-10°C reading through the last recorded measurement at the end of the chain.
   Harvest-to-precool field heat — the most thermally damaging part of most cold chains —
   is left out on purpose. Any arrival freshness reported on this site is therefore an
   **upper bound**: real arrival freshness is likely somewhat lower than what any
   observation scenario, including a full temperature history, would infer. See
   [Cold-chain arrival model](/store/cold-chain-arrival).

2. **Arrival families are assumed, not fitted, on six shipments.** The duration and
   temperature distributions used to generate arrival freshness are hand-authored
   parametric shapes, chosen to be roughly consistent with six real shipments. They are
   not a Maximum Likelihood Estimation (MLE) fit — a statistical method for finding the
   parameters that best explain observed data — because six data points can't support a
   fitting claim, and the model documents this explicitly. Treat the shape of these
   distributions as a documented modeling choice, not a measured fact about the real cold
   chain. See [Cold-chain arrival model](/store/cold-chain-arrival) and
   [Why a pack date does so much](./why-pack-date).

3. **The profit and cost figures are illustrative, not calibrated to a real store.** The
   sell price, purchase cost, waste cost, and stockout penalty used throughout this site
   are a deliberately chosen set of synthetic numbers, not measurements taken from an
   actual grocer's books. Read any dollar figure on this site as relative and
   illustrative, not as a real profit forecast. See
   [Does the money follow?](./does-money-follow) and
   [Profit accounting](/economics/profit-accounting).

4. **The ordering policy only plans a few days ahead, not the berries' whole shelf
   life.** The controller decides how much to order by weighing expected demand and
   freshness only through the next delivery — a few days out — rather than reasoning over
   the full ~10-day shelf life of the fruit. This short-sightedness is the most likely
   reason a sharper freshness belief doesn't translate into more profit in the results on
   [Does the money follow?](./does-money-follow): the policy simply isn't built to act on
   information about spoilage that's further out than it already looks.

5. **Strawberry cold-chain data stands in for blueberry transit.** The only open
   multi-shipment, multi-position, harvest-started berry pallet temperature dataset
   available — six real refrigerated shipments logged by Abdella, Brecht & Uysal (2021) —
   is a strawberry logger study, not a blueberry-specific one. This substitution is
   deliberate. Blueberry-specific *kinetics* — Q10 (an Arrhenius-style rule from food
   science: spoilage roughly multiplies by Q10 for every 10°C rise in temperature) and
   reference shelf life — still come from blueberry-specific sources. Only the
   thermal-path shapes — how long transit takes and how much temperature varies along the
   way — are borrowed from the strawberry loggers. This is worth revisiting if an open
   blueberry pallet-logger dataset of comparable detail appears.

6. **The freshness-decay model is a smooth idealization.** Freshness loss is modeled as a
   continuously accumulating random process (a Gamma Process, described on
   [How fruit loses freshness: the gamma process](/store/gamma-aging)). Real berry
   spoilage is partly *discrete* — a single bruise, or mould spreading fruit-to-fruit
   within a punnet. A process where spoilage events arrive randomly and can cluster
   together would describe that better than smooth accumulation does. The smooth version
   is the more defensible of the two conventions considered here, not a claim of
   biological exactness.

7. **A studio temperature-bias control doesn't reach the displayed arrival chart.** The
   studio includes a control meant to let you explore "what if this corridor ran warmer or
   colder" — a corridor here means the shipping-route / transit-assumption profile a
   delivery uses. That control does change the simulated deliveries used elsewhere on the
   site. It does not, however, change the arrival-freshness chart shown to you in the
   studio: moving the control shifts the underlying simulation but leaves that one chart
   unchanged. This is a known display gap rather than a hidden one — adding a
   bias-shifted version of that chart is a real, if still unbuilt, follow-up.

8. **The studio's corridor selector only offers the default blend, not the individual
   corridors underneath it.** The corridor picker shows a single option, "Abdella mix" —
   the production default, a blend of a short-haul and a long-haul route profile. The
   pooled and individual route profiles that make up that blend are still fitted to the
   same six real shipments, but none of them is currently selectable on its own; only the
   blended default is.

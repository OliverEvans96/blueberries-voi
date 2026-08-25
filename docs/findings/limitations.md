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

Every other page on this site describes what the model does; this one gathers what it
deliberately doesn't, or can't yet, do, in one place instead of scattered as footnotes.
None of these are hidden defects: each is a considered scope decision or a known gap, and
most already have a caveat on the page where they're most relevant. This page exists so a
reader doesn't have to hunt across the whole site to get the full list at once.

> **Figure (coming soon):** a single annotated timeline of one delivery's journey —
> harvest, field heat (out of scope), refrigerated leg (modeled), shelf life (modeled) —
> with each limitation on this page pinned to the stage of the journey or the modeling
> step it applies to.

## The idea

Treat this as a checklist for reading any result on this site with the right amount of
skepticism, not as a reason to distrust the model wholesale. Some of these are hard scope
boundaries chosen deliberately (refrigerated-leg-only scope); some are honest consequences
of a small dataset (six shipments); some are known display or wiring gaps not yet closed
(a studio bias knob that doesn't reach one chart); and one is an idealization common to
almost every survival-analysis model in this space (a smooth aging process standing in
for partly-discrete spoilage).

## The math

This page is a synthesis, not a new derivation — the quantitative claims below (the 98.4%
duration share, the uncalibrated cost constants, the six-shipment sample size) are each
sourced from, and derived on, the page that owns them; see the cross-links in each item.

## Why it's modelled this way

Not a single modeling choice — each item below is its own decision, made for its own
reasons, described on its own page. What's consistent across all of them is a project-wide
preference: state a limitation plainly and move on, rather than quietly shipping a model
that looks more capable than the underlying evidence supports.

## In the code

| Limitation | Where it's enforced / visible | File:line |
| --- | --- | --- |
| Refrigerated-leg-only scope (arrival `f` is an upper bound) | Arrival window excludes field heat | `data/abdella/arrival_model.json` (`provenance.window`); see [Cold-chain arrival model](/store/cold-chain-arrival) |
| Arrival families assumed, not fitted, on n=6 shipments | `provenance.notes`: "Hand-authored assumed families... Not MLE-fitted" | `data/abdella/arrival_model.json` |
| Studio corridor bias knob not applied to the displayed prior chart | `transit_temp_bias_c` parameter, accepted but unused | `crates/voi_core/src/arrival_wire.rs:69-81` (applied to truth path at `crates/voi_core/src/session.rs:318`, explicitly not applied in `arrival_summary_wire`) |
| Only the default mixed corridor is tied to the six real shipments | `abdella_all` corridor vs. illustrative `short_haul`/`long_haul` chips | `data/abdella/arrival_model.json` (`corridors`, `provenance.notes`); studio chips at `web/src/controls.ts:315-317` |

## Caveats

The items below are the limitations themselves — each is a caveat by nature, so this
section *is* the list rather than a coda to it.

1. **Refrigerated-leg-only scope.** The model covers only the segment from first
   below-10°C reading through the published end-of-chain measurement. Harvest-to-precool
   field heat — the most thermally damaging part of most cold chains — is out of scope by
   choice. Arrival freshness reported anywhere on this site is therefore an **upper
   bound**: real arrival freshness is likely somewhat lower than what any observation
   scenario, including a full temperature trace, would infer. See
   [Cold-chain arrival model](/store/cold-chain-arrival).

2. **Arrival families are assumed, not fitted, on n=6 shipments.** The duration and
   temperature distributions used to generate arrival freshness are hand-authored
   parametric families set to be roughly consistent with six real shipments — not an MLE
   fit, and explicitly documented as not one, because six data points can't support a
   fitting claim. Treat the shape of these distributions as a documented modeling choice,
   not a measured fact about the real cold chain. See
   [Cold-chain arrival model](/store/cold-chain-arrival) and
   [Why a pack date does so much](./why-pack-date).

3. **The profit-cost scaffold is uncalibrated.** Unit margin, waste cost, and stockout
   penalty are a shared scaffold (`DEFAULT_PROFIT_COSTS`), explicitly flagged as
   uncalibrated, not fitted to any real grocer's economics. Any dollar figure on this site
   should be read as relative/illustrative, not as a real profit forecast. This is one of
   the leading candidate reasons profit doesn't yet track belief accuracy cleanly; see
   [Does the money follow?](./does-money-follow) and
   [Profit accounting](/economics/profit-accounting).

4. **Strawberry cold-chain data stands in for blueberry transit.** The only open
   multi-shipment, multi-position, harvest-started berry pallet temperature dataset
   available (Abdella, Brecht & Uysal 2021) is a strawberry logger study, not a
   blueberry-specific one. This substitution is deliberate — blueberry *kinetics* ($q_{10}$,
   reference life) still come from blueberry-specific sources; only the thermal-path
   ensemble (duration and temperature-spread shapes) is borrowed from the strawberry
   loggers. It's worth revisiting if an open blueberry pallet-logger dataset of comparable
   resolution appears.

5. **The gamma-process aging law is a smooth idealization.** Freshness loss is modeled as
   a continuously-accumulating random process (shape-scaled gamma decrements). Real berry
   spoilage is partly *discrete* — a single bruise, or mould spreading fruit-to-fruit
   within a punnet — which would be better described by a compound-Poisson or
   contagion-style process. Shape-scaling is the more defensible of the two gamma
   conventions considered, not a claim of biological exactness. See
   [How fruit ages: the gamma process](/store/gamma-aging).

6. **A studio temperature-bias knob doesn't reach the displayed arrival chart.**
   `transit_temp_bias_c` — a studio control meant to let a user explore "what if the
   corridor ran warmer/colder" — is wired into the simulated *truth* path (it biases the
   truth-path temperature draw before freshness is generated), but the code comment on
   `arrival_summary_wire` states plainly that the same bias is "accepted for call-site
   stability but not applied here": the arrival-freshness-prior chart shown to the user
   doesn't shift when this knob is moved, even though the underlying simulated deliveries
   do. This is a known display gap, not a hidden one — the source comment calls out that
   adding a bias-shifted variant of the displayed curve is a real extension, left as a
   follow-up.

7. **The short-haul/long-haul corridor chips are illustrative, not calibrated.** The
   studio's corridor selector offers three chips — "All six" (the default), "Long-haul",
   and "Short-haul." Only the default (`abdella_all`) is the corridor whose parameters
   were anchored against the six real Abdella shipments' calibrated moments; the
   short-haul and long-haul corridors are documented in the arrival artifact's own
   provenance notes as "illustrative studio corridors only" — useful for exploring how the
   model responds to a different corridor shape, not representative of any measured route.

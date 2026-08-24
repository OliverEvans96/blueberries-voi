---
title: "Demand: a calendar, not a coin"
sources:
  code: [crates/voi_core/src/demand_profile.rs, crates/voi_core/src/physics.rs, crates/voi_core/src/params.rs, crates/voi_core/src/policy.rs]
---

# Demand: a calendar, not a coin

How many customers buy blueberries on a given day isn't a flat average with a bit of noise sprinkled on — real grocery demand has a weekly rhythm (weekends busier than midweek) and a slower drift across the weeks, and even after accounting for both of those, the day-to-day count is noisier than a simple random count would be. This page covers where that shape comes from and, just as importantly, what every ordering policy in this project is — and isn't — allowed to know about it.

> **Figure (coming soon):** a bar chart of $\mu(\text{day})$ over one ~13-week window, showing the day-of-week sawtooth riding on top of the slower week-to-week drift.

## The idea

Demand here has two layers. The first is a **known shape**: a repeating day-of-week pattern (some days just draw more shoppers than others) multiplied by a slower week-to-week factor (some weeks are busier than others across the whole window). That shape isn't invented — it's fit from a real retail dataset and then scaled so the *average* day lands around 30 units of demand.

The second layer is **noise on top of the shape**: even knowing perfectly what an average Tuesday looks like, no two Tuesdays are identical. The model doesn't just add ordinary Poisson noise around the day's mean (which would make the count fairly predictable once you knew the mean) — it uses a more overdispersed distribution, so daily demand swings more than a simple counting process would predict, matching how real retail demand tends to behave.

## The math

The mean demand for a given day is

$$
\mu(\text{day}) = \text{scale\_target\_mu} \times \text{dow\_factor}[\text{day} \bmod 7] \times \text{week\_factor}\!\left[\min(\lfloor \text{day} / 7 \rfloor,\ W-1)\right]
$$

where day $0$ is Monday, `dow_factor` is a length-7 table of day-of-week multipliers, `week_factor` is a table of $W$ slower multipliers (one per calendar week in the fitted window, held flat past the last observed week), and `scale_target_mu` sets the overall level. With the committed defaults (`scale_target_mu = 30.0`, day-of-week factors starting at $0.971$ for Monday and rising through the weekend, week factors starting near $0.84$ and drifting up over the window) this gives, for example, $\mu(0) = 24.32$ (a below-average Monday in a below-average opening week) and $\mu(6) = 29.48$ (Sunday, the week's peak day-of-week factor).

Given that day's mean $\mu$, the actual demand draw $X$ is negative binomial, implemented as a gamma-Poisson mixture — a two-stage draw that produces more spread than a plain Poisson with the same mean:

$$
r = \frac{\mu}{\text{vm} - 1}, \qquad p = \frac{r}{r+\mu}, \qquad \lambda \sim \mathrm{Gamma}\!\left(r,\ \frac{1-p}{p}\right), \qquad X \sim \mathrm{Poisson}(\lambda)
$$

where $\text{vm}$ (variance-to-mean ratio) is the demand overdispersion, live default $\text{vm} = 2.0$ — meaning the variance of the day's demand is about twice its mean, rather than equal to it (which is what a plain Poisson would give). The live demand profile also ships from `Dingdong-Inc/FreshRetailNet-50K`, a real Chinese fresh-retail dataset, mean-normalized: the fitted shape is real, but the underlying `sale_amount` units are not blueberry punnets and were rescaled to hit the operational $\mu \approx 30$ target, not measured directly.

## Why it's modelled this way

Demand structure — the day-of-week × week factors — is known to every policy: every ordering policy in the project, including every baseline and every oracle, sees the *same* calendar mean $\mu(\text{day})$ for a given day. None of them forecast or estimate demand from past sales. Inferring demand jointly with the freshness state was set aside deliberately, because it would confound forecasting skill with ordering skill and undermine the thing this whole project is trying to isolate — that differences in outcome come from *freshness* information, not from one policy being better at guessing tomorrow's footfall.

That's the point worth being explicit about: because $\mu(\text{day})$ is common knowledge to every policy on every rung of the observation ladder, any profit or accuracy gap measured across the ladder is attributable to what each rung knows about *freshness*, not to demand-forecasting differences — the calendar is a fixed backdrop, not a competitive variable.

The demand shape comes from a Chinese retail dataset rather than a US one because no public, granular, day-level US blueberry sales series was available to fit against, while FreshRetailNet-50K offers real day-of-week and censoring structure for a comparable premium, high-velocity perishable category, during a window (March–June) that sits in China's *peak* domestic blueberry season. What transfers is deliberately narrow: the **shape** (day-of-week rhythm, within-window drift, stockout censoring pattern) is treated as usable; the **absolute scale**, unit prices, pack sizes, and store-delivery logistics are not — the model borrows a rhythm, not a market.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Calendar mean for a day | $\mu(\text{day})$ | `crates/voi_core/src/demand_profile.rs:95` ([`DemandProfile::mu`](/api/rust/voi_core/demand_profile/struct.DemandProfile.html#method.mu)) |
| Resolve calendar mean vs. legacy flat mean | — | `crates/voi_core/src/params.rs:69` ([`demand_mu_for_day`](/api/rust/voi_core/params/struct.ModelParams.html#method.demand_mu_for_day)) |
| Overall level (committed default `30.0`) | scale_target_mu | `data/freshnet/demand_profile.json` (`scale_target_mu`) |
| Day-of-week / week multiplier tables | dow_factor, week_factor | `data/freshnet/demand_profile.json` (`dow_factors`, `week_factors`) |
| Overdispersion (committed default `2.0`) | vm | `data/freshnet/demand_profile.json` (`demand_vm`); field default `crates/voi_core/src/params.rs:46` |
| Negative-binomial demand draw (gamma-Poisson mixture) | $r$, $p$, $\lambda$, $X$ | `crates/voi_core/src/physics.rs:508` (`draw_demand_from_mu`), mixture sampler `crates/voi_core/src/spawn_rng.rs:71` ([`negative_binomial_gamma_poisson`](/api/rust/voi_core/spawn_rng/fn.negative_binomial_gamma_poisson.html)) |
| Every ordering policy reads the same calendar mean (no forecasting) | — | `crates/voi_core/src/policy.rs:133` (`protection_demand_quantile`, calls `demand_mu_for_day`) |
| Dataset provenance | — | `data/freshnet/demand_profile.json` (`dataset_id: "Dingdong-Inc/FreshRetailNet-50K"`) |

## Caveats

- The demand shape is fit from Chinese fresh-retail data, not blueberry-specific US sales; only the day-of-week/seasonal *shape* and censoring pattern are meant to transfer, not absolute unit counts, prices, or logistics.
- The fitted window covers roughly March–June of one year — a single season, not a full annual cycle, so any seasonality beyond that window is out of sample.
- Overdispersion ($\text{vm} = 2.0$) is one fixed number for the whole window and every day, not fit separately per day-of-week or per week.
- Because every policy shares the identical calendar mean, this model cannot say anything about how a store would fare if it had to *forecast* demand rather than merely order under known-but-random demand — that comparison is out of scope by construction.

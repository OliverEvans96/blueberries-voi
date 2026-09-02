---
title: "Demand: a calendar, not a coin"
sources:
  code: [crates/voi_core/src/demand_profile.rs, crates/voi_core/src/physics.rs, crates/voi_core/src/params.rs, crates/voi_core/src/policy.rs]
---

# Demand: a calendar, not a coin

How many customers buy blueberries on a given day isn't just a flat average with random noise on top. Real grocery demand has a weekly rhythm — weekends are busier than midweek — plus a slower drift across the weeks. Even after accounting for both patterns, the day-to-day count is still noisier than a simple random count would be. This page covers where that shape comes from. It also covers what every ordering policy in this project is allowed to know about it — and, just as importantly, what it isn't.

## The idea

Demand here has two layers. The first is a **known shape**: a repeating day-of-week pattern — some days just draw more shoppers than others — multiplied by a slower week-to-week factor, since some weeks are busier than others across the whole window. That shape isn't invented. It's fit from a real retail dataset and then scaled so the average day lands around 30 units of demand.

The second layer is **noise on top of the shape**. Even knowing exactly what an average Tuesday looks like, no two Tuesdays are identical. The model doesn't just add ordinary Poisson noise around the day's mean, which would make the count fairly predictable once you knew the mean. Instead it uses a more spread-out (overdispersed) distribution, so daily demand swings more than a simple counting process would predict — matching how real retail demand tends to behave.

## The math

Demand follows both a weekly rhythm and a slower drift across the weeks in the fitted window. We capture that as: the mean demand on a given day equals a baseline level, times a day-of-week multiplier, times a week-to-week multiplier.

$$
\mu(\text{day}) = \mu_0 \times d\!\left(\text{day} \bmod 7\right) \times w\!\left(\min(\lfloor \text{day} / 7 \rfloor,\ W-1)\right)
$$

Here $\mu_0$ is the overall baseline level, $d(\cdot)$ is the day-of-week multiplier (a table of seven values, one per weekday), and $w(\cdot)$ is the slower week-to-week multiplier (one value per calendar week in the fitted window, held flat once you run past the last of the $W$ observed weeks). Day $0$ is Monday.

With the model's default values — a baseline level of 30.0, day-of-week factors starting at $0.971$ for Monday and rising through the weekend, and week factors starting near $0.84$ and drifting upward over the window — this works out to, for example, an average of $\mu(0) = 24.32$ units on day 0 (a below-average Monday in a below-average opening week) and $\mu(6) = 29.48$ units on day 6 (Sunday, the week's peak day).

Given that day's mean, the actual number of units sold is drawn from a negative binomial distribution. It's implemented as a two-stage gamma-Poisson mixture: first a random rate is drawn from a Gamma distribution centered on the day's mean, then the actual count is drawn from a Poisson distribution using that rate. This two-stage process produces more spread than a plain Poisson draw with the same mean would.

$$
r = \frac{\mu}{v - 1}, \qquad p = \frac{r}{r+\mu}, \qquad \lambda \sim \mathrm{Gamma}\!\left(r,\ \frac{1-p}{p}\right), \qquad X \sim \mathrm{Poisson}(\lambda)
$$

Here $\mu$ is that day's mean demand from above; $v$ is the variance-to-mean ratio — how much more spread out demand is than its average alone would suggest; $r$ and $p$ are the two parameters of the underlying gamma distribution; $\lambda$ is the randomly drawn rate; and $X$ is the resulting demand draw for the day. The model's default value for $v$ is $2.0$ — meaning the variance of a day's demand is about twice its mean, rather than equal to it, which is what a plain Poisson distribution would give.

The demand shape itself comes from `Dingdong-Inc/FreshRetailNet-50K`, a real Chinese fresh-retail dataset, mean-normalized to this store's scale. The fitted shape is real, but the dataset's own sales-count units aren't blueberry punnets — they were rescaled to hit the operational target of about 30 units a day, not measured directly from blueberry sales.

## Why it's modelled this way

Demand structure — the day-of-week and week-to-week factors — is known to every policy. Every ordering policy in this project, including every baseline and even a hypothetical observer who's told the true state of every unit (an "oracle"), sees the same calendar mean for a given day. None of them forecast or estimate demand from past sales.

This was a deliberate choice. Inferring demand jointly with the freshness state was set aside on purpose, because it would confound forecasting skill with ordering skill. That would undermine the thing this whole project is trying to isolate: whether differences in outcome come from freshness information, not from one policy simply being better at guessing tomorrow's footfall.

This point is worth stating plainly. Because the calendar mean is common knowledge to every policy under every scenario on the observation ladder, any profit or accuracy gap measured across the ladder can only come from what each scenario knows about freshness. It can't come from demand-forecasting differences, because there aren't any — the calendar is a fixed backdrop, not something policies compete on.

The demand shape comes from a Chinese retail dataset rather than a US one for a simple reason: no public, granular, day-level US blueberry sales data was available to fit against. FreshRetailNet-50K, by contrast, offers real day-of-week and stockout patterns for a comparable premium, fast-moving perishable category. Its data window (March–June) also happens to sit in China's peak domestic blueberry season.

What transfers from this dataset is deliberately narrow. The **shape** — day-of-week rhythm, drift within the window, the pattern of stockout censoring — is treated as usable. The **absolute scale**, unit prices, pack sizes, and store-delivery logistics are not. The model borrows a rhythm, not a market.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Calendar mean for a day | $\mu(\text{day})$ | `crates/voi_core/src/demand_profile.rs:114` ([`DemandProfile::mu`](/api/rust/voi_core/demand_profile/struct.DemandProfile.html#method.mu)) |
| Resolve calendar mean vs. legacy flat mean | — | `crates/voi_core/src/params.rs:96` ([`demand_mu_for_day`](/api/rust/voi_core/params/struct.ModelParams.html#method.demand_mu_for_day)) |
| Overall baseline level, $\mu_0$ (default value `30.0`) | scale_target_mu | `data/freshnet/demand_profile.json` (`scale_target_mu`) |
| Day-of-week multiplier $d(\cdot)$ / week multiplier $w(\cdot)$ | dow_factor, week_factor | `data/freshnet/demand_profile.json` (`dow_factors`, `week_factors`) |
| Overdispersion, variance-to-mean ratio $v$ (default value `2.0`) | vm | `data/freshnet/demand_profile.json` (`demand_vm`); field default `crates/voi_core/src/params.rs:73` |
| Negative-binomial demand draw (gamma-Poisson mixture) | $r$, $p$, $\lambda$, $X$ | `crates/voi_core/src/physics.rs:551` (`draw_demand_from_mu`), mixture sampler `crates/voi_core/src/spawn_rng.rs:83` ([`negative_binomial_gamma_poisson`](/api/rust/voi_core/spawn_rng/fn.negative_binomial_gamma_poisson.html)) |
| Every ordering policy reads the same calendar mean (no forecasting) | — | `crates/voi_core/src/policy.rs:143` (`protection_demand_quantile`, calls `demand_mu_for_day`) |
| Dataset provenance | — | `data/freshnet/demand_profile.json` (`dataset_id: "Dingdong-Inc/FreshRetailNet-50K"`) |

## Caveats

- The demand shape is fit from Chinese fresh-retail data, not blueberry-specific US sales. Only the day-of-week and seasonal shape, plus the censoring pattern, are meant to transfer — not absolute unit counts, prices, or logistics.
- The fitted window covers roughly March–June of one year — a single season, not a full annual cycle — so any seasonality beyond that window is out of sample.
- Overdispersion (variance-to-mean ratio of $2.0$) is one fixed number for the whole window and every day. It isn't fit separately per day-of-week or per week.
- Because every policy shares the identical calendar mean, this model can't say anything about how a store would fare if it had to forecast demand rather than simply order under known-but-random demand. That comparison is out of scope by construction.

---
title: Cold-Chain Arrival Model
sources:
  code:
    - crates/voi_core/src/arrival.rs
    - crates/voi_core/src/physics.rs
    - data/abdella/arrival_model.json
    - scripts/arrival_calibration_note.py
    - data/abdella/calibration_note.md
---

# Cold-chain arrival model

Every delivery starts its life in the store already partway degraded, because it spent a day or several inside a truck before it ever reached a shelf. This page describes how the simulator turns "a shipment travelled through a refrigerated corridor" into a probability distribution over each unit's freshness `f` the moment it arrives. It matters because every observation rung in the knowledge ladder (P0 through F3) is a different amount of information about the *same* underlying trip, not a different model — get the generative story right here and the whole ladder's information gains become meaningful.

![Six Abdella cold-chain shipments (duration vs. mean temperature factor) plotted against the corridor families the arrival model assumes](/figures/cold-chain-arrival-calibration-overlay.png)

## The idea

Think of one delivery as a truck making one trip. Two things about the trip are shared by every berry on the truck: how many days the trip took, and (bundled into one number) how warm the truck ran on average. Those two shared quantities combine into a single number called **cumulative thermal exposure**, `Lambda` (Λ) — think of it as "how many equivalent days of reference-temperature aging did this trip cost," measured in reference-days. A short, cold trip might cost 2 reference-days; a long, warm one might cost 9.

But not every berry on the truck experiences the trip identically — pallets aren't perfectly isothermal, and a unit near a warm corner ages a little faster than one in the coldest pocket. That per-unit wobble is captured by a **position multiplier** `psi` (ψ), drawn separately for every single unit. Multiplying the trip's shared exposure by a unit's personal `psi` gives that unit's own exposure, which then feeds into the *same* random-degradation law used for in-store aging (a gamma-distributed loss). The result is a **freshness** `f` for that one unit — not an age, a state variable running from 1 (pristine) down to 0 (spoiled/dead).

So the model has one "corridor" story (duration and average temperature) shared across the whole delivery, and one "which pallet spot did this berry ride in" story that's private to each unit. No observation the store ever makes — not even a full temperature log — reveals that private per-unit story, which is why units from the very same lot can genuinely differ in freshness even under perfect knowledge of the trip's temperature history.

## The math

For one delivery drawn from a **corridor** (an arrival lane, e.g. `short_haul`, `long_haul`, or the fitted `abdella_all`), the truth-path generative model draws, per unit:

$$
d = d_{\min} + \mathrm{Gamma}(\text{delay\_shape}, \text{delay\_scale})
$$

$d$ is the calendar transit duration in days; $d_{\min}$, delay_shape, and delay_scale are properties of the chosen corridor. Transit duration is drawn once per delivery (all units on the same truck share the same trip length).

$$
\bar T \sim \mathrm{TruncatedNormal}(\mu_T, \sigma_T,\ \text{floor} = T_{\text{floor}})
$$

$\bar T$ is the delivery's mean transit temperature in °C, also drawn once per delivery, truncated below at a physical floor (the reefer can't usefully run colder than its floor).

$$
\bar\varphi = q_{10}^{(\bar T - T_{\mathrm{ref}})/10}
$$

`phi_bar` ($\bar\varphi$) is the duration-averaged Q10 temperature factor — how much faster (or slower) than the reference temperature $T_{\mathrm{ref}}$ this trip's average temperature drives degradation. $q_{10}$ is the Q10 coefficient (rate multiplier per 10°C of warming).

$$
\psi \sim \mathrm{LogNormal}(0, \sigma_{\text{pos}})
$$

$\psi$ is the within-pallet position multiplier, drawn **independently for every unit** (unlike $d$ and $\bar T$, which are shared across the delivery).

$$
\Lambda = d \cdot \bar\varphi \cdot \psi
$$

$\Lambda$ (cumulative thermal exposure, in reference-days) is this unit's personal exposure: the shared trip exposure ($d \cdot \bar\varphi$) scaled by its own position multiplier.

$$
D \sim \mathrm{Gamma}(k \cdot \Lambda,\ \theta), \qquad f = \max(0,\ 1 - D)
$$

$D$ is the per-unit degradation loss, drawn from the *same* shape-scaled gamma law used for day-by-day in-store aging (shape scaled by exposure, not scale) — a trip is just more warped time for the same underlying process. $k$ (gamma_shape) and $\theta$ (gamma_scale) are the two gamma-law parameters; $f$, arrival freshness, is what's left after subtracting the draw, floored at zero.

Because it's the same gamma law, the closed forms used for in-store aging apply directly to arrival freshness conditional on exposure $\Lambda$:

$$
P(f > x \mid \Lambda) = \gamma_p(k\Lambda,\ (1-x)/\theta)
$$

$$
P(f = 0 \mid \Lambda) = \gamma_q(k\Lambda,\ 1/\theta)
$$

where $\gamma_p$ and $\gamma_q$ are the regularized lower and upper incomplete gamma functions (the same CDF machinery reused, not reimplemented, for arrival). The second line is the exact atom of mass at $f=0$ — the probability a unit arrives already spoiled — available in closed form with no simulation needed.

**Live calibrated numbers** (from `data/abdella/arrival_model.json`, schema version 1):

| Parameter | Symbol | Value |
| --- | --- | --- |
| Mean transit temperature | $\mu_T$ | 2.7 °C |
| Transit temperature spread | $\sigma_T$ | 0.4 °C |
| Temperature floor | $T_{\text{floor}}$ | 0.0 °C |
| Position spread | $\sigma_{\text{pos}}$ | 0.08 |
| Q10 coefficient | $q_{10}$ | 3.0 |
| Reference temperature | $T_{\mathrm{ref}}$ | 0.0 °C |
| Gamma shape | $k$ (gamma_shape) | 2.0 |
| Gamma scale | $\theta$ (gamma_scale) | 1/28 ≈ 0.035714 |
| Reference life | $\eta_{\text{ref}}$ | 14.0 reference-days |

Note that $k \cdot \theta \cdot \eta_{\text{ref}} = 2.0 \times \tfrac{1}{28} \times 14 = 1$ — this is the single calibration invariant that ties the gamma law's mean loss rate to a 14-reference-day shelf life, shared between transit and in-store aging.

**Corridors** (`d_min`, delay_shape, delay_scale — the shifted-gamma duration law):

| Corridor | $d_{\min}$ (days) | delay_shape | delay_scale |
| --- | --- | --- | --- |
| `short_haul` | 1.5 | 2.0 | 0.25 |
| `long_haul` | 3.5 | 4.0 | 0.5 |
| `abdella_all` | 1.9 | 3.0 | 1.0 |

`short_haul` and `long_haul` are illustrative studio corridors; `abdella_all` is the one roughly calibrated against the six real Abdella shipments.

## Why it's modelled this way

**Shape-scaling, not scale-scaling.** The daily in-store aging law and the arrival law both scale the gamma distribution's *shape* parameter by exposure ($\mathrm{Gamma}(k\Lambda, \theta)$), rather than its *scale*. Arrhenius kinetics describe a rate constant, meaning heat produces *more* degradation events of the same size, not the same number of *bigger* events. Shape-scaling is also what makes $\Lambda$ a genuine sufficient statistic for the whole trip — two journeys with equal $\Lambda$ but different temperature paths have the same freshness distribution under shape-scaling, but would differ under scale-scaling, which would mean a temperature log couldn't be summarized by one number at all. It also makes transit (one continuous exposure) and shelf life (a daily loop) the same process observed at different granularities. The honest caveat: the gamma process is itself an idealization — real spoilage is partly discrete (a bruise, mould spreading to a neighboring berry), which a compound-Poisson or contagion model would capture better than a continuous gamma subordinator. Shape-scaling is the more defensible of the two gamma conventions available, not a claim of physical exactness.

**Assumed families, not a fit.** With only six real refrigerated shipments in hand, the parameters in `arrival_model.json` were **hand-authored** — round, interpretable numbers chosen to roughly bracket the six observed (duration, `phi_bar`) points — not fit by maximum likelihood. An MLE fit on six points would produce numbers that *look* validated by data when they aren't; the calibration note is explicit that "the data does not validate these families" and the calibration script performs no fitting step, only an overlay plot. The six shipments actually observed (`data/abdella/calibration_note.md`):

| shipment | duration $d$ (days) | $\bar\varphi$ |
| --- | --- | --- |
| S1 | 4.604 | 1.318 |
| S2 | 1.903 | 1.287 |
| S3 | 6.243 | 1.355 |
| S4 | 5.347 | 1.433 |
| S5 | 6.514 | 1.286 |
| S6 | 4.083 | 1.478 |

One shipment's position probes (S4) were excluded from the $\sigma_{\text{pos}}$ calibration as suspect — S4's recorded position-probe temperature factor implied a sustained temperature well above anything the lot-mean trace supported, so it was flagged and left out rather than silently averaged in.

**Alternatives considered:** scale-scaling everywhere misreads Q10 as event severity rather than event frequency, and breaks $\Lambda$-sufficiency. Separate gamma rates for transit vs. shelf would let the two conventions drift apart from each other over time. Fitting the six shipments by MLE would over-read six data points as validation. And a lower reference life would leave most corridors delivering fruit that's mostly dead on arrival, leaving no rung anything to learn.

## In the code

| Concept | Symbol | Location |
| --- | --- | --- |
| Truth-path per-unit generative draw | $d, \bar T, \bar\varphi, \psi, \Lambda, D, f$ | `crates/voi_core/src/arrival.rs:448` ([`draw_unit_f`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.draw_unit_f)) |
| Whole-delivery truth draw (shared $d$, $\bar T$; per-unit $\psi$/loss) | — | `crates/voi_core/src/arrival.rs:471` ([`draw_truth_delivery`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.draw_truth_delivery)) |
| Q10 temperature factor | $\bar\varphi = q_{10}^{(\bar T-T_{\mathrm{ref}})/10}$ | `crates/voi_core/src/arrival.rs:366` ([`phi_bar_from_t_bar`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.phi_bar_from_t_bar)), calling `crates/voi_core/src/physics.rs:31` ([`store_temp_factor`](/api/rust/voi_core/physics/fn.store_temp_factor.html)) |
| Tail probability given exposure | $P(f>x\mid\Lambda)=\gamma_p(k\Lambda,(1-x)/\theta)$ | `crates/voi_core/src/arrival.rs:400` ([`p_f_gt_at`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.p_f_gt_at)) |
| Full CDF given exposure | $P(f\le x\mid\Lambda)$ | `crates/voi_core/src/arrival.rs:411` ([`cdf_f_given_lambda`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.cdf_f_given_lambda)) |
| Exact spoiled-on-arrival atom | $P(f=0\mid\Lambda)=\gamma_q(k\Lambda,1/\theta)$ | `crates/voi_core/src/arrival.rs:426` ([`p_f_zero`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.p_f_zero)) |
| Regularized incomplete gamma functions | $\gamma_p, \gamma_q$ | `crates/voi_core/src/physics.rs:125` ([`gamma_p`](/api/rust/voi_core/physics/fn.gamma_p.html)), `:140` (`gamma_q`) |
| Position multiplier draw (per unit) | $\psi$ | `crates/voi_core/src/arrival.rs:442` (`draw_psi_pos`) |
| Truncated-normal transit temperature draw | $\bar T$ | `crates/voi_core/src/arrival.rs:431` (`sample_truncated_normal`) |
| Calibrated artifact (live numbers, corridors) | all of the above | `data/abdella/arrival_model.json` |
| Reporting-only calibration overlay (no fitting) | six-shipment table + figure | `scripts/arrival_calibration_note.py`, `data/abdella/calibration_note.md` |

## Caveats

**Refrigerated-leg only — arrival freshness is an upper bound.** The model window runs from the first lot-mean temperature reading below 10 °C through the published end-of-chain point. Harvest-to-precool field heat — typically the most thermally damaging segment of the whole chain — is excluded entirely. Real arrival freshness is therefore lower, likely meaningfully lower, than what this model reports. Extending the model to cover field heat would need its own segment, its own data treatment, and a harvest-date observation rung; it's a deliberate scope choice for now, not an oversight.

**No observation channel ever reveals a unit's actual freshness.** Even the richest available observation — the full temperature-history trace — pins down the shared exposure $\Lambda$ for the delivery exactly. It never reveals $\psi$ (the per-unit position multiplier) or the per-unit gamma draw $D$. That is a hard floor on how sharp any belief about one specific unit's freshness can ever get, no matter how much is observed about the trip — and it's exactly why units within a single lot genuinely differ in freshness even under perfect trip knowledge.

**Assumed, not fitted.** The corridor and distribution-family parameters are hand-authored to be roughly consistent with six real shipments, not statistically validated by them. Treat the specific numbers as a defensible starting point, not a calibrated fact about real cold chains.

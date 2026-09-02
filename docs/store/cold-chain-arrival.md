---
title: Cold-Chain Arrival Model
sources:
  code:
    - crates/voi_core/src/arrival.rs
    - crates/voi_core/src/shipments.rs
    - crates/voi_core/src/physics.rs
    - data/abdella/arrival_model.json
    - scripts/arrival_calibration_note.py
    - data/abdella/calibration_note.md
  adr: ["0149", "0150", "0148"]
---

# Cold-chain arrival model

Every delivery starts its life already partway degraded, because it spent a day or several inside a truck before it ever reached a shelf. This page describes how the simulator turns "a shipment travelled through a refrigerated corridor" into a probability distribution over each unit's freshness the moment it arrives. It matters because every scenario on the site's 5-rung observation ladder — from books only through the temperature-history scenario — is a different *amount of information* about the same underlying trip, not a different model. Get this generative story right and the whole ladder's information gains become meaningful.

## The idea

Think of one delivery as a truck making one trip. Three things about the trip are shared by every berry on the truck, plus one thing that's private to each unit:

1. **How long the trip took** — calendar transit duration, drawn once per delivery from a corridor's duration curve. A corridor here just means the shipping-route / transit-assumption profile a delivery uses (how long it typically takes, how variable that is).
2. **What happened thermally along the way** — a temperature path built from a few fixed cold-chain legs, plus occasional random *break events* (unrefrigerated dock time, a missed connection, a door left open). The path's cumulative thermal exposure, written Λ (lambda), is computed from that full path rather than drawn as a single number up front.
3. **How much this particular unit differs from its lot-mates** — a per-unit multiplier ψ (psi), drawn independently for every unit. The model calls the spread of this multiplier *inter-lot position noise*: even units from the very same batch don't all arrive at exactly the same freshness.

Multiplying the trip's shared exposure by a unit's own ψ gives that unit's personal exposure, which feeds into the same random-degradation law used for in-store freshness loss. The result is a **freshness** value for that unit — not a calendar clock, but a state variable running from 1 (just-picked) down to 0 (spoiled).

So the model has one "corridor" story (duration and temperature path) shared across the whole delivery, and one private "how did this particular berry fare" story for each unit. No observation the store ever makes — not even a full temperature log — reveals that private per-unit story, which is why units from the very same lot can genuinely differ in freshness even under perfect knowledge of the trip's temperature history.

### Three lots per delivery

Each delivery is modeled as three separate lots, rather than one big pool of units, so the filter can tell delivery-to-delivery variation apart from the smaller variation within a single truckload. Total case quantity is split across the three lots, not multiplied, so this doesn't slow the filter down. Each lot draws its own upstream journey (its own duration, its own break events), but all three lots share one final leg from the distribution center to the store:

$$
\Lambda_\ell = \Lambda_{\mathrm{upstream},\ell} + \Lambda_{\mathrm{shared}}
$$

When the store has an LGTIN for each case — a Global Trade Item Number (GTIN) plus a batch/lot number, identifying one production batch of one product, distinct from the whole delivery — the filter can track each of the three lots' arrival belief separately. Without it (the Universal Product Code, or UPC, scenarios), the store can't tell the three lots apart, so the filter instead uses one blended distribution across all three: `Law_UPC = (1/L) Σ_ℓ Law(record_ℓ)` — mixing the three lots' distributions together, not averaging their pack dates. The simulator draws all three lot ids for a delivery at once, matching this three-lot picture.

A more detailed transit model — with per-leg timing built bottom-up and trip-level temperature variation — is a planned future refinement; the sections below describe what the model does today.

## The math

For one delivery drawn from a corridor — `abdella_mix` is the production default, a mixture of two corridor shapes; `abdella_all` is a single curve fit to all six real refrigerated shipments used to calibrate this model (we'll call these the six calibration shipments) — the generative model proceeds as follows.

### Duration

$$
d = d_{\min} + \mathrm{Gamma}(\text{delay\_shape}, \text{delay\_scale})
$$

$d$ is calendar transit duration in days, drawn once per delivery. $d_{\min}$, the shape, and the scale are properties of the chosen corridor. With probability 0.78, the draw instead reuses one of the six calibration shipments' actual durations (plus a little added noise) rather than drawing purely from the curve above — so real historical variability, not just the analytic tail, drives most draws.

### Cold-chain path and breaks

The baseline path walks three named legs in order, each holding a fixed setpoint temperature for its share of $d$:

| Leg | Share $w_k$ | Setpoint $\mu_k$ |
| --- | --- | --- |
| `precool_staging` | 0.15 | 0.35 °C |
| `line_haul` | 0.60 | 2.58 °C |
| `dock_receiving` | 0.25 | 4.32 °C |

On top of that baseline, random break events are drawn — occasional stretches where the temperature jumps up for a while:

$$
N \sim \mathrm{Poisson}(\rho \cdot d), \qquad
\tau_j \sim \mathrm{Exp}(\bar\tau) \text{ at fixed } T_{\mathrm{break}}
$$

Here $N$ is how many breaks happen on the trip, and each break $j$ lasts $\tau_j$ days at a fixed break temperature $T_{\mathrm{break}}$. Break start times are spread uniformly across the trip; each break raises the temperature to $T_{\mathrm{break}}$ for its duration, clamped so total break time never exceeds the trip length. The trip clock keeps running during breaks, so the total exposure works out exactly to:

$$
\Lambda_{\mathrm{lot}} = d \cdot \varphi_{\mathrm{set}} + \sum_j \tau_j \cdot (\varphi_{\mathrm{break}} - \varphi_{\mathrm{set}})
$$

where $\varphi_{\mathrm{set}}$ is the duration-weighted Q10 factor of the leg baseline, and $\varphi_{\mathrm{break}}$ is the same factor evaluated at the break temperature. Q10 is an Arrhenius-style rule from food science: spoilage roughly multiplies by Q10 for every 10°C rise in temperature. Given $N$, the break contribution follows a Gamma distribution with shape $N$ and scale $m = \bar\tau \cdot (\varphi_{\mathrm{break}} - \varphi_{\mathrm{set}})$.

The model always builds the full temperature trace first, then computes exposure from it — the trace is the fundamental object, not a fit to some already-decided exposure number. An earlier design worked the other way around (picking one "average trip temperature" and forcing a trace to match it); the "Why it's modelled this way" section below explains why that made the temperature-history scenario less useful.

### Per-unit position and freshness

$$
\psi \sim \mathrm{LogNormal}(0, \sigma_{\text{pos}})
$$

$\psi$ is drawn independently for every unit — this is the inter-lot position noise described above.

$$
\Lambda = \Lambda_{\mathrm{lot}} \cdot \psi
$$

$$
D \sim \mathrm{Gamma}(k \cdot \Lambda,\ \theta), \qquad f = \max(0,\ 1 - D)
$$

$D$ is the per-unit freshness loss, drawn from the same shape-scaled gamma law used for in-store freshness loss. Conditional on the unit's exposure $\Lambda$:

$$
P(f > x \mid \Lambda) = \gamma_p(k\Lambda,\ (1-x)/\theta), \qquad
P(f = 0 \mid \Lambda) = \gamma_q(k\Lambda,\ 1/\theta)
$$

### Calibrated numbers

The table below comes from the project's calibration artifact:

| Parameter | Symbol | Value |
| --- | --- | --- |
| Break temperature | $T_{\mathrm{break}}$ | 12.0 °C |
| Break rate | $\rho$ | 0.08 /day |
| Mean break duration | $\bar\tau$ | 0.5 days |
| Inter-lot position noise | $\sigma_{\text{pos}}$ | 0.08 |
| Q10 coefficient | $q_{10}$ | 2.0 |
| Reference temperature | $T_{\mathrm{ref}}$ | 0.0 °C |
| Gamma shape | $k$ | 2.0 |
| Gamma scale | $\theta$ | 1/28 ≈ 0.035714 |
| Reference shelf life (arrival draw) | $\eta_{\text{ref,arrival}}$ | 14.0 reference-days |

Two of these numbers tie this model directly to the in-store freshness model used everywhere else on the site: the reference shelf life (14 days) and Q10 (2.0) both apply to in-store freshness loss and to this arrival model — one shared shelf-life setting for the whole trip, store included. Leg setpoints (0.35 / 2.58 / 4.32 °C for precool, line-haul, and dock) come from the six calibration shipments.

Duration variability comes from `abdella_mix`, a mixture of about 63% short-haul-style trips and 37% long-haul-style trips (rounded to 60/40 in the product's interface). That split reproduces the spread seen across the six calibration shipments, and it's tuned to keep the books-only scenario's duration belief meaningfully wider than the pack-date scenario's — so the observation ladder shows a real information gain at that step.

**Corridors** (shape of each corridor's duration curve):

| Corridor | $d_{\min}$ (days) | delay_shape | delay_scale |
| --- | --- | --- | --- |
| `short_haul` | 1.803 | 2.0 | 0.05 |
| `long_haul` | 4.033 | 1.628 | 0.814 |
| `abdella_all` | 1.853 | 3.009 | 0.974 |

**Corridor mixtures** (the categorical trip-type draw that happens before duration):

| Mixture | Components | Role |
| --- | --- | --- |
| `abdella_mix` | 0.627 × `short_haul` + 0.373 × `long_haul` | Production default; short-haul matches one calibration shipment, long-haul matches the other five |

`abdella_all` is a single curve fit to all six calibration shipments pooled together; `short_haul` and `long_haul` are the two per-regime curves that `abdella_mix` blends.

Break rate, mean break duration, and break temperature are assumed rather than fitted — none of the six calibration shipments experienced a break, so there was nothing to fit them to.

## Why it's modelled this way

**Scaling the gamma's shape, not its size.** Both daily in-store freshness loss and this arrival model scale a gamma distribution's *shape* parameter by cumulative thermal exposure, rather than its *scale*. That mirrors the underlying food-science idea behind Q10: heat produces *more* degradation events of the same size, not the same number of bigger events. It also means cumulative exposure Λ is a genuine sufficient statistic for the whole trip — the one number the model actually needs, with nothing lost by summarizing a trip this way. Two trips with the same Λ but different temperature paths end up with the same freshness distribution; under the other kind of scaling they wouldn't, and a temperature log couldn't be boiled down to one number at all.

**Random break events instead of a wider temperature draw.** An earlier design (design record ADR 0148) simply made the "how warm did it run" draw wider. But at a spread that matched the six calibration shipments, that left only about 1.6% of the trip's exposure variability attributable to temperature — nearly all of it came from duration — so a temperature log would have told the store almost nothing it didn't already know from timing alone. A later revision, ADR 0150, replaced that draw with occasional random cold-chain breaks at a fixed elevated temperature instead, raising temperature's share of that variability to a design target of about 20%, so the temperature-history scenario actually has something new to teach the store. ADR 0148's duration-fitting work still stands; only its transit-temperature approach was superseded.

**Building the temperature trace first, then computing exposure from it.** This keeps the thing the model randomizes and the thing a temperature-history observation would show identical — a full trace, not a summary. The retired alternative worked in the opposite order and made a temperature log much less informative once the pack date was already known.

**Assumed vs. fitted parameters.** With only six real refrigerated shipments to work from, corridor durations are matched to the shipments' overall statistics, and leg temperature setpoints are chosen so a break-free trip matches the shipments' observed average. Break rate and break duration are documented modeling assumptions, not fitted values — none of the six shipments actually experienced a break, so there's nothing to fit them to. Trying to fit six data points any more precisely would be reading more into the data than it can support.

## In the code

| Concept | Symbol | Location |
| --- | --- | --- |
| Truth-path temperature trace (legs + breaks) | path → Λ | `crates/voi_core/src/shipments.rs:98` ([`truth_transit_trace`](/api/rust/voi_core/shipments/fn.truth_transit_trace.html)) |
| Exposure from observed path | Λ | `crates/voi_core/src/arrival.rs:2334` ([`resolve_arrival_exposure`](/api/rust/voi_core/arrival/fn.resolve_arrival_exposure.html)) |
| Truth draw: path then Λ | — | `crates/voi_core/src/arrival.rs:1335` ([`draw_transit`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.draw_transit)) |
| Whole-delivery truth draw (single- and three-lot) | $d$, trace, Λ; per-unit $\psi$/loss | `crates/voi_core/src/arrival.rs:1402` ([`draw_truth_delivery`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.draw_truth_delivery)); three-lot version is `draw_truth_multilot_delivery_biased` |
| Truth-path per-unit generative draw | $d$, breaks, $\psi$, $\Lambda$, $f$ | `crates/voi_core/src/arrival.rs:1375` ([`draw_unit_f`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.draw_unit_f)) |
| Break-free baseline factor | $\varphi_{\mathrm{set}}$ | `crates/voi_core/src/arrival.rs:1088` ([`phi_set`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.phi_set)) |
| Closed-form Λ given break durations | — | `crates/voi_core/src/arrival.rs:1120` ([`lambda_from_breaks`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.lambda_from_breaks)) |
| Filter: enumerate break counts + gamma quadrature | — | `crates/voi_core/src/arrival.rs:1633` (`thermal_nodes_for_key`) |
| Q10 temperature factor | $\phi(T)$ | `crates/voi_core/src/physics.rs:38` ([`store_temp_factor`](/api/rust/voi_core/physics/fn.store_temp_factor.html)) |
| Tail probability given exposure | $P(f>x\mid\Lambda)$ | `crates/voi_core/src/arrival.rs:1297` ([`p_f_gt_at`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.p_f_gt_at)) |
| Full CDF given exposure | $P(f\le x\mid\Lambda)$ | `crates/voi_core/src/arrival.rs:1309` ([`cdf_f_given_lambda`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.cdf_f_given_lambda)) |
| Spoiled-on-arrival atom | $P(f=0\mid\Lambda)$ | `crates/voi_core/src/arrival.rs:1324` ([`p_f_zero`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.p_f_zero)) |
| Gamma quantile (break enumeration) | — | `crates/voi_core/src/arrival.rs:664` (`gamma_dist_quantile`) |
| Position multiplier draw | $\psi$ | `crates/voi_core/src/arrival.rs:1369` (`draw_psi_pos`) |
| Artifact fields: legs, $T_{\mathrm{break}}$, $\rho$, $\bar\tau$, corridors | — | `data/abdella/arrival_model.json`; parsed by `crates/voi_core/src/arrival.rs:578` ([`arrival_artifact_from_json`](/api/rust/voi_core/arrival/fn.arrival_artifact_from_json.html)) |
| Pre-baked default belief curve for fast startup | — | `crates/voi_core/src/arrival_prior_baked.rs`; loaded when its fingerprint matches the saved artifact; rebuilt at runtime if Q10 or $T_{\mathrm{ref}}$ change ([`sync_params`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.sync_params)) |
| Reporting overlay (no fitting) | six-shipment table + figure | `scripts/arrival_calibration_note.py`, `data/abdella/calibration_note.md` |

## Caveats

**Refrigerated-leg only — arrival freshness is an upper bound.** The model window runs from the first lot-mean temperature reading below 10 °C through the published end-of-chain point. Harvest-to-precool field heat — typically the most thermally damaging segment — is excluded. Real arrival freshness is therefore lower than what this model reports.

**No observation channel reveals a unit's actual freshness.** Even the richest channel — the full temperature-history trace — pins down the shared exposure Λ for the delivery (or per-lot Λ under the three-lot model). It never reveals a unit's own ψ or its individual gamma draw $D$.

**Break parameters are assumed, not measured.** The six calibration shipments never experienced a break; the break rate and mean break duration are scenario knobs, not measurements. At a break rate near zero, the model should recover the clean-chain duration dominance seen in the data; at the default break rate, duration's share of the trip's total exposure variability is a design output (about 80%), not something measured from the calibration shipments.

**Today's leg model is simpler than a full bottom-up one.** The code currently splits each trip into fixed leg *shares* of a single drawn duration, rather than drawing each leg's own duration independently and summing them. A more detailed, bottom-up version — with independent per-leg timing and trip-level temperature variation — is a planned future refinement, while keeping the same break model and filter caching approach described above.

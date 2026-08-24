---
title: Model parameters
sources:
  adr: [0144, 0041, 0080, 0112, 0122]
  code:
    - crates/voi_core/src/params.rs
    - crates/voi_core/src/demand_profile.rs
    - crates/voi_core/src/session.rs
    - crates/voi_core/src/policy.rs
    - crates/voi_core/src/arrival.rs
    - crates/voi_core/src/schedule.rs
    - crates/voi_core/src/rollout.rs
    - web/src/controls.ts
    - web/src/mock/generate.ts
    - data/abdella/arrival_model.json
    - data/freshnet/demand_profile.json
---

# Model parameters

Every number the simulator runs on — how fast fruit spoils, how variable demand is, how
cautious the ordering policy is, how big a look-ahead the controller uses — has a default
value baked into the code. This page is the single place that lists them, what they mean in
plain language, and exactly where in the repository each one is set, so a reader can check a
claim in a figure or a report against the source of truth.

> **Figure (coming soon):** a labeled diagram of one delivered lot's journey — pack date to
> store receipt — showing where $d$ (transit duration), $\bar T$ (mean transit temperature),
> $\bar\phi$ (duration-averaged Q10 factor), $\psi$ (within-pallet position multiplier) and
> $\Lambda$ (cumulative thermal exposure) each apply, with $\eta_\text{ref}$ marked as the
> reference life those exposures are measured against.

![Assumed arrival-model families plotted against the six-shipment Abdella sample: duration-averaged temperature factor phi_bar vs. refrigerated-leg duration, no curve fitted](/figures/arrival-calibration-overlay.png)

*The arrival model's temperature/duration parameters (below) are hand-authored assumed
families, not fit to this six-shipment sample — the plot above is a sanity check, not a
regression.*

## The idea

The parameters fall into a few natural groups:

- **Physics** — how fast a unit of fruit loses freshness, and how temperature accelerates
  that loss.
- **Arrival** — how fresh (or spoiled) a delivered lot is by the time it reaches the store,
  as a function of the corridor (arrival lane) it travelled.
- **Demand** — how many units customers want to buy each day, and how that varies.
- **Belief / filter** — the size and shape of the internal representation the particle
  filter uses to track what's on the shelf when it can't observe everything directly.
- **Control** — how the ordering policy decides how much to order, including its
  look-ahead simulation (rollout).
- **Economics** — the dollar figures the studio uses to score outcomes.
- **Studio / episode** — scheduling and session-length knobs that shape one interactive run.

Two things are worth flagging up front. First, `eta_ref` (reference life) and `gamma_scale`
are not independent — the code derives one from the other so that a unit's *expected* daily
freshness loss stays anchored to a single stated shelf life. Second, several "studio" defaults
(particle count, rollout horizon, price/cost inputs) live in the TypeScript front end rather
than in `ModelParams`, because they are session-level UI choices, not physical model
parameters — the tables below label each row `Rust (ModelParams)` or `Studio (TS)` accordingly.

## The math

Freshness $f \in [0,1]$ decays via a daily gamma-distributed decrement. The shape parameter
$k$ (`gamma_shape`) and scale parameter $\theta$ (`gamma_scale`) are tied to the reference
life $\eta_\text{ref}$ (`eta_ref`, in reference-days) by one invariant:

$$
k \cdot \theta \cdot \eta_\text{ref} = 1 \quad\Longrightarrow\quad \theta = \frac{1}{k \cdot \eta_\text{ref}}
$$

With the defaults $k = 2.0$ and $\eta_\text{ref} = 14$ reference-days, $\theta = 1/28 \approx
0.035714$, giving a mean daily loss of $k\theta = 1/14 \approx 0.0714$ freshness units per
reference-day at the reference temperature $T_\text{ref}$.

Temperature accelerates aging through a Q10 factor, shared by the in-store clock and the
arrival (transit) clock:

$$
\phi(T) = Q_{10}^{\,(T - T_\text{ref})/10}
$$

where $Q_{10}$ (`q10`) is the rate multiplier per 10°C of warming and $T_\text{ref}$
(`t_ref_c`) is the shared zero point of the thermal scale. In store, the daily decrement draw
is $\text{Gamma}(k\cdot\phi(T_\text{store}),\,\theta)$ — a *shape*-scaled gamma, not a
scale-scaled one (see below).

For a delivered lot, cumulative thermal exposure over the transit leg is

$$
\Lambda = d \cdot \bar\phi \cdot \psi
$$

where $d$ is the calendar transit duration (days), $\bar\phi = \phi(\bar T)$ is the
duration-averaged Q10 factor evaluated at the lot's mean transit temperature $\bar T$, and
$\psi$ is a within-pallet position multiplier drawn log-normally, $\psi = \exp(z\cdot
\sigma_\text{pos})$ with $z\sim\mathcal N(0,1)$. Arrival freshness for a unit is then a draw
against $\text{Gamma}(k\cdot\Lambda,\,\theta)$ — the same shape-scaled family as the in-store
clock, so $\Lambda$ is a genuine sufficient statistic for "how much of the journey's thermal
exposure has this unit absorbed."

## Why it's modeled this way

ADR 0144 settles two things this table depends on. First, aging is **shape-scaled**
($\text{Gamma}(k\phi,\theta)$), not **scale-scaled** ($\text{Gamma}(k,\theta\phi)$): heat is
read as producing *more* degradation events of the same size (Arrhenius: a rate constant),
not fewer, larger ones. The two conventions agree on the mean and disagree on the variance,
and only shape-scaling keeps $\Lambda$ a sufficient statistic for the journey and keeps the
transit and in-store clocks reconcilable as the same process observed over different amounts
of warped time.

Second, `gamma_scale` is *derived* from `eta_ref` and `gamma_shape` rather than set
independently, so the two shelf-life numbers the repo used to carry — $\eta_\text{ref}=14$
days and an un-reconciled $1/(k\theta)$ that used to work out to 6.25 days — can't drift apart
again. The alternative (leaving `gamma_scale = 0.08` hard-coded, as it still is in one
JS mock module — see Caveats) was rejected because it silently made transit degradation
14× too cheap on some code paths and quietly capped mean shelf life at 6.25 reference-days,
well below the literature-defensible 14-day figure for blueberries at 0°C.

**Honest caveat (from the ADR itself):** the gamma process is an idealization. Real spoilage
is partly discrete — a bruise, or mould spreading fruit-to-fruit — and better described by a
compound Poisson or contagion process than by a continuous subordinator. Shape-scaling is the
more defensible of the two continuous conventions available, not a claim of physical
exactness. The arrival-model temperature/position family (`mu_T`, `sigma_T`, `sigma_pos`) is
also explicitly **hand-authored, not MLE-fitted** — the underlying sample is six shipments,
too few to fit a distribution to with any confidence.

## In the code

All defaults below were read directly from the current source; "Rust (ModelParams)" rows are
in `crates/voi_core/src/params.rs` unless noted, "Studio (TS)" rows are UI/session defaults
that live in TypeScript and are not part of `ModelParams` itself.

### Physics (aging)

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Reference life | $\eta_\text{ref}$ | 14.0 | reference-days | Shelf-life scale at $T_\text{ref}$; fixes mean daily loss jointly with $k$ | `crates/voi_core/src/params.rs:40` |
| Gamma shape | $k$ | 2.0 | — | Shape of the daily/arrival gamma decrement draw | `crates/voi_core/src/params.rs:50` |
| Gamma scale | $\theta$ | $1/28\approx0.035714$ (derived) | — | $\theta = 1/(k\cdot\eta_\text{ref})$; recomputed by `set_reference_life()` | `crates/voi_core/src/params.rs:62-64` |
| Q10 coefficient | $Q_{10}$ | 3.0 | ×/10°C | Rate multiplier per 10°C above $T_\text{ref}$ | `crates/voi_core/src/params.rs:41` |
| Reference temperature | $T_\text{ref}$ | 0.0 | °C | Shared zero point of the thermal-exposure scale | `crates/voi_core/src/params.rs:42` |
| Store temperature | $T_\text{store}$ | 4.0 | °C | Assumed constant retail-display temperature | `crates/voi_core/src/params.rs:43` |
| Picking exponent | $\sigma$ | 0.5 | — | Power-law freshness-selectivity in picking weights, $w \propto f^\sigma$ | `crates/voi_core/src/params.rs:44`, `crates/voi_core/src/physics.rs:360-368` |

### Demand and logistics

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Demand mean | $\mu$ | 30.0 | units/day | Negative-binomial mean demand: flat legacy default `demand_mu`; the calendar profile's own scale is the separate `scale_target_mu` field | `crates/voi_core/src/params.rs:45` (`demand_mu`); `crates/voi_core/src/demand_profile.rs:106` ([`scale_target_mu`](/api/rust/voi_core/demand_profile/struct.DemandProfile.html#method.scale_target_mu)); `data/freshnet/demand_profile.json` |
| Demand variance-to-mean | $V/M$ | 2.0 | — | NB dispersion: variance $= (V/M)\times$ mean | `crates/voi_core/src/params.rs:46`; `data/freshnet/demand_profile.json` |
| Case size | — | 8 | units/case | Orders round up to whole cases | `crates/voi_core/src/params.rs:47` |
| Units per lot | — | 15 | units/lot | Virtual grid width per delivered lot on the $L\times U$ truth/filter grid | `crates/voi_core/src/params.rs:9,53` |
| Lead time | — | 1 | days | Days between order placement and delivery | `crates/voi_core/src/session.rs:113` |
| Delivery weekdays | — | Mon, Wed, Fri | weekday set | Calendar days deliveries can arrive on | `crates/voi_core/src/schedule.rs:10-13` |

### Belief / particle filter

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Belief lot count | $L$ | 10 | lots | Virtual lot slots tracked in the flattened belief | `crates/voi_core/src/params.rs:6`; `crates/voi_core/src/session.rs:121` |
| Belief histogram bins | $K$ | 4 | bins | Freshness histogram bins per lot slot | `crates/voi_core/src/session.rs:122` (studio session default); `crates/voi_core/src/session.rs:1163` (RPC default) |
| Particle count | $N$ | 200 | particles | Particles in the unit-level particle filter's belief bank | Studio (TS) `web/src/controls.ts:133`; RPC default `crates/voi_core/src/session.rs:1066` |

### Control / ordering

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Service quantile | $\alpha$ | 0.9 | probability | Target service fractile for the base-stock order-up-to level | `crates/voi_core/src/session.rs:640`; Studio (TS) `web/src/controls.ts:128` |
| Damping | $\rho$ | 0.8 | — | Smooths day-to-day changes in the damped survival-weighted order | `crates/voi_core/src/session.rs:641`; Studio (TS) `web/src/controls.ts:129` |
| Rollout horizon | $H$ | 7 | days | Look-ahead length for the rollout controller's forward simulation | `crates/voi_core/src/session.rs:110`; Studio (TS) `web/src/controls.ts:130` |
| Rollout paths | — | 2 | paths | CRN sample paths per candidate order evaluated in rollout | `crates/voi_core/src/session.rs:111`; Studio (TS) `web/src/controls.ts:131` |
| Candidate case radius | — | 1 | cases | Case-steps above/below the base order the rollout search considers | `crates/voi_core/src/session.rs:112`; Studio (TS) `web/src/controls.ts:132` |
| Protection-demand MC sample count | $n_\text{mc}$ | 20,000 | samples | Monte Carlo draws for the heterogeneous protection-period demand quantile | `crates/voi_core/src/policy.rs:10` |

### Economics (studio)

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Sell price | $p_\text{sell}$ | \$4.50 | \$/unit | Studio revenue per unit sold | Studio (TS) `web/src/mock/generate.ts:17` |
| Unit cost | $c_\text{unit}$ | \$1.80 | \$/unit | Studio purchase cost per unit | Studio (TS) `web/src/mock/generate.ts:18` |
| Waste cost | $c_\text{waste}$ | \$1.20 | \$/unit | Studio cost per unit wasted | Studio (TS) `web/src/mock/generate.ts:19` |
| Stockout cost | $c_\text{stockout}$ | \$2.50 | \$/unit | Studio penalty per unit of unmet demand | Studio (TS) `web/src/mock/generate.ts:20` |
| Rollout margin / waste / stockout costs | — | 2.0 / 1.5 / 3.0 | \$/unit | *Separate* internal costs used only by the Rust rollout controller's own look-ahead objective — not the studio P&L figures above | `crates/voi_core/src/rollout.rs:26-39` ([`RolloutCosts::default`](/api/rust/voi_core/rollout/struct.RolloutCosts.html#method.default)) |

### Episode / studio session

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Episode horizon | — | 90 | days | Length of one studio episode (ADR 0122) | `crates/voi_core/src/session.rs:290`; Studio (TS) `web/src/mock/generate.ts:43` (`window_days`) |
| Default corridor | — | `abdella_all` | corridor key | Default arrival corridor (lane) selected | `crates/voi_core/src/params.rs:33,53` |

### Arrival-model artifact (`data/abdella/arrival_model.json`)

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Mean transit temperature | $\mu_T$ | 2.7 | °C | Mean of the truncated-normal transit temperature law | `data/abdella/arrival_model.json`; field `mu_t` at `crates/voi_core/src/arrival.rs:74` |
| Transit temperature spread | $\sigma_T$ | 0.4 | °C | SD of the truncated-normal transit temperature law | `data/abdella/arrival_model.json`; field `sigma_t` at `crates/voi_core/src/arrival.rs:75` |
| Temperature floor | — | 0.0 | °C | Left-truncation floor of the transit temperature law | `data/abdella/arrival_model.json`; field `temp_floor_c` at `crates/voi_core/src/arrival.rs:76` |
| Position spread | $\sigma_\text{pos}$ | 0.08 | log-scale | Log-normal spread of $\psi$, the within-pallet position multiplier | `data/abdella/arrival_model.json`; field `sigma_pos` at `crates/voi_core/src/arrival.rs:77` |
| Default corridor (`abdella_all`) | $d_\text{min}$ / delay shape / delay scale | 1.9 days / 3.0 / 1.0 | days / — / days | Minimum transit duration and gamma delay-tail shape for the composite corridor | `data/abdella/arrival_model.json` (`corridors.abdella_all`) |

## Caveats

- This table lists **defaults** — nearly every physics and demand parameter is exposed as a
  studio slider and can be changed at runtime; a session's actual parameters may differ from
  what's shown here.
- **Confirmed drift:** `web/src/mock/generate.ts` (the browser-side mock/demo aging path,
  separate from the live Rust/wasm engine) still hard-codes `GAMMA_SCALE = 0.08`
  (`web/src/mock/generate.ts:25`) — the pre-ADR-0144 value. The canonical value, derived in
  Rust from `eta_ref` and `gamma_shape`, is $1/28\approx0.035714$. Anything computed through
  that mock path will not match the live engine's shelf-life calibration.
- `short_haul` and `long_haul` corridors in the arrival-model artifact are explicitly
  documented as "illustrative studio corridors only" in the artifact's own provenance notes —
  not calibrated lanes, unlike `abdella_all`.
- The arrival-model temperature/position family is fit to **six shipments** — not enough data
  to support a confident distributional claim; treat `mu_T`, `sigma_T`, and `sigma_pos` as
  assumptions, not measurements.
- Rollout's internal `RolloutCosts` (margin/waste/stockout = 2.0/1.5/3.0) are a *separate*
  set of numbers from the studio P&L economics (`p_sell`/`c_unit`/`c_waste`/`c_stockout`) —
  changing one does not change the other, and conflating them will misread what the rollout
  controller is actually optimizing against.

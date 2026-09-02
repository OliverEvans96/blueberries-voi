---
title: Model parameters
sources:
  code:
    - crates/voi_core/src/params.rs
    - crates/voi_core/src/demand_profile.rs
    - crates/voi_core/src/session.rs
    - crates/voi_core/src/policy.rs
    - crates/voi_core/src/arrival.rs
    - crates/voi_core/src/shipments.rs
    - crates/voi_core/src/schedule.rs
    - crates/voi_core/src/rollout.rs
    - web/src/controls.ts
    - web/src/mock/generate.ts
    - data/abdella/arrival_model.json
    - data/freshnet/demand_profile.json
  adr: ["0149", "0150", "0148"]
---

# Model parameters

Every number the simulator runs on — how fast fruit spoils, how variable demand is, how
cautious the ordering policy is, how big a look-ahead the controller uses — has a default
value in the code. This page lists them, what they mean in plain language, and where in the
repository each one is set, so a reader can check a claim in a figure or report against the
source of truth.

## The idea

The parameters fall into a few natural groups:

- **Physics** — how fast a unit of fruit loses freshness, and how temperature accelerates
  that loss.
- **Arrival** — how fresh (or spoiled) a delivered lot is by the time it reaches the store,
  depending on the corridor it travelled — the shipping-route / transit-assumption profile a
  delivery uses.
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
than in the core Rust parameter set, because they are session-level UI choices, not physical
model parameters — the tables below label each row `Rust (ModelParams)` or `Studio (TS)`
accordingly.

## The math

Freshness $f \in [0,1]$ decays through a daily gamma-distributed decrement: a smooth decay
curve that only moves downward, never bouncing back up, until it reaches zero. The shape
parameter $k$ (`gamma_shape`) and scale parameter $\theta$ (`gamma_scale`) are tied to the
reference life $\eta_\text{ref}$ (`eta_ref`, the shelf life in reference-days at the reference
temperature) by one invariant:

$$
k \cdot \theta \cdot \eta_\text{ref} = 1 \quad\Longrightarrow\quad \theta = \frac{1}{k \cdot \eta_\text{ref}}
$$

With the defaults $k = 2.0$ and $\eta_\text{ref} = 14$ reference-days, $\theta = 1/28 \approx
0.035714$, giving a mean daily loss of $k\theta = 1/14 \approx 0.0714$ freshness units per
reference-day at the reference temperature $T_\text{ref}$.

Temperature speeds up freshness loss through a Q10 factor — an Arrhenius-style rule from food
science: spoilage roughly multiplies by Q10 for every 10°C rise in temperature. The same
factor is shared by the in-store clock and the arrival (transit) clock:

$$
\phi(T) = Q_{10}^{\,(T - T_\text{ref})/10}
$$

where $Q_{10}$ (`q10`) is the rate multiplier per 10°C of warming and $T_\text{ref}$
(`t_ref_c`) is the shared zero point of the thermal scale. In store, the daily decrement draw
is $\text{Gamma}(k\cdot\phi(T_\text{store}),\,\theta)$ — temperature scales the *shape* of the
gamma distribution here, not its *scale* (see "Why it's modeled this way" below).

For a delivered lot, cumulative thermal exposure over the transit leg is built from a full
temperature path over the trip, not a single mean-temperature draw. Calendar duration is

$$
d = d_{\min} + \mathrm{Gamma}(\text{delay\_shape}, \text{delay\_scale})
$$

drawn from the chosen corridor. A deterministic three-leg baseline (precool / line-haul /
dock) holds fixed temperature setpoints for shares of that duration. On top of this baseline,
**cold-chain breaks** — a stop, a door left open, any lapse that lets temperature spike — are
added as $N \sim \mathrm{Poisson}(\rho d)$ episodes, where $\rho$ is the break hazard (how
often a break happens per transit-day), each lasting a mean duration $\bar\tau$ (`tau_bar`) at
a fixed break temperature $T_{\mathrm{break}}$. These episodes are punched into the
temperature path as rectangular pulses. Lot-level exposure is then

$$
\Lambda_{\mathrm{lot}} = d \cdot \varphi_{\mathrm{set}} + \sum_j \tau_j \cdot (\varphi_{\mathrm{break}} - \varphi_{\mathrm{set}})
$$

— baseline exposure over the whole trip, plus the extra exposure each break episode $j$
contributes above baseline — integrated equivalently from the full temperature trace in code.
Per-unit exposure adds one more source of randomness: $\Lambda = \Lambda_{\mathrm{lot}} \cdot
\psi$, where $\psi = \exp(z \cdot \sigma_\text{pos})$ with $z \sim \mathcal{N}(0,1)$ is a
small multiplicative nudge representing inter-lot position noise — the idea that a given
lot's units don't all arrive at exactly the same freshness. Arrival freshness is then a draw
against $\text{Gamma}(k\cdot\Lambda,\,\theta)$, the same shape-scaled family as the in-store
clock.

Each delivery is modeled as three separate lots, with each lot's exposure split into an
upstream component and a shared component, $\Lambda_\ell = \Lambda_{\mathrm{upstream},\ell} +
\Lambda_{\mathrm{shared}}$. Splitting a delivery into lots this way — rather than treating the
whole delivery as one uniform block — lets the filter tell delivery-to-delivery variation
apart from unit-to-unit variation within a single delivery; a delivery's total units are split
across its three lots, not multiplied. A more detailed transit model — with bottom-up stage
durations, trip-level thermal modes, and finer path noise, while keeping this same break law —
is a planned future refinement (see [cold-chain arrival](/store/cold-chain-arrival)).

## Why it's modeled this way

This page's math rests on two design choices.

Aging is **shape-scaled** ($\text{Gamma}(k\phi,\theta)$) rather than **scale-scaled**
($\text{Gamma}(k,\theta\phi)$): heat is modeled as producing *more* degradation events of the
same size — an Arrhenius-style rate effect — rather than fewer, larger ones. The two
conventions agree on the mean freshness loss and disagree on its variance. Only shape-scaling
keeps $\Lambda$ (cumulative thermal exposure) a sufficient statistic for the journey — the one
number the freshness-decay draw actually needs, with nothing lost by summarizing the whole
temperature history down to it — and keeps the transit and in-store clocks reconcilable as the
same underlying process, just observed over different amounts of warped time.

`gamma_scale` is *derived* from `eta_ref` and `gamma_shape` rather than set independently, so
the two numbers can't drift apart. One JS mock module hard-codes `gamma_scale = 0.08` instead
of deriving it (see Caveats). That shortcut makes transit degradation roughly 14 times too
cheap on some code paths. It also caps mean shelf life at 6.25 reference-days — well below the
14-day figure that's defensible in the literature for blueberries at 0°C.

**Caveat.** The gamma process is an idealization. Real spoilage is partly discrete — a bruise,
or mould spreading fruit-to-fruit — and is arguably better described by a process where events
like this arrive randomly and can cluster together (a compound Poisson, or contagion-style
process) than by this smooth, continuous decay curve. Shape-scaling is simply the more
defensible of the two continuous conventions available here, not a claim of physical
exactness. The arrival-model break parameters ($\rho$, the break hazard; $\bar\tau$, mean
break duration; $T_{\mathrm{break}}$, the break temperature) and the leg setpoints are assumed
or anchored to plausible values, not fitted from data by maximum-likelihood estimation (the
standard statistical method for picking the parameters that best explain observed data). Only
the corridor durations are moment-matched — calibrated so the model's mean and variance line
up with the data's — to the six real refrigerated shipments used to calibrate corridor timing
(referred to on this page, and in the underlying data files, as the Abdella shipments). An
earlier version of the model instead fit a single truncated-normal draw for transit
temperature per shipment; that approach has been replaced by the current legs-plus-breaks
model described above, because a single draw per trip can't represent that temperature changes
over the course of a trip and can spike temporarily during a break. The retired `mu_T` /
`sigma_T` fields are no longer used.

## In the code

All defaults below were read directly from the current source; "Rust (ModelParams)" rows are
in `crates/voi_core/src/params.rs` unless noted, "Studio (TS)" rows are UI/session defaults
that live in TypeScript and are not part of the core Rust parameter set itself.

### Physics (aging)

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Reference life | $\eta_\text{ref}$ | 14.0 | reference-days | Shelf-life scale at $T_\text{ref}$; fixes mean daily loss jointly with $k$ | `crates/voi_core/src/params.rs:67` |
| Gamma shape | $k$ | 2.0 | — | Shape of the daily/arrival gamma decrement draw | `crates/voi_core/src/params.rs:77` |
| Gamma scale | $\theta$ | $1/28\approx0.035714$ (derived) | — | $\theta = 1/(k\cdot\eta_\text{ref})$; recomputed by `set_reference_life()` | `crates/voi_core/src/params.rs:89-91` |
| Q10 coefficient | $Q_{10}$ | 2.0 | ×/10°C | Rate multiplier per 10°C above $T_\text{ref}$ | `crates/voi_core/src/params.rs:68` |
| Reference temperature | $T_\text{ref}$ | 0.0 | °C | Shared zero point of the thermal-exposure scale | `crates/voi_core/src/params.rs:69` |
| Store temperature | $T_\text{store}$ | 4.0 | °C | Assumed constant retail-display temperature | `crates/voi_core/src/params.rs:70` |
| Picking exponent | $\sigma$ | 0.5 | — | Power-law freshness-selectivity in picking weights, $w \propto f^\sigma$ | `crates/voi_core/src/params.rs:71`, `crates/voi_core/src/physics.rs:379-388` |

### Demand and logistics

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Demand mean | $\mu$ | 30.0 | units/day | Negative-binomial mean demand: flat legacy default `demand_mu`; the calendar profile's own scale is the separate `scale_target_mu` field | `crates/voi_core/src/params.rs:72` (`demand_mu`); `crates/voi_core/src/demand_profile.rs:127` ([`scale_target_mu`](/api/rust/voi_core/demand_profile/struct.DemandProfile.html#method.scale_target_mu)); `data/freshnet/demand_profile.json` |
| Demand variance-to-mean | $V/M$ | 2.0 | — | Negative-binomial dispersion: variance $= (V/M)\times$ mean | `crates/voi_core/src/params.rs:73`; `data/freshnet/demand_profile.json` |
| Case size | — | 8 | units/case | Orders round up to whole cases | `crates/voi_core/src/params.rs:74` |
| Units per lot | — | 15 | units/lot | Virtual grid width per delivered lot on the $L\times U$ truth/filter grid | `crates/voi_core/src/params.rs:13,56` |
| Lead time | — | 1 | days | Days between order placement and delivery | `crates/voi_core/src/session.rs:229` |
| Delivery weekdays | — | Mon, Wed, Fri | weekday set | Calendar days deliveries can arrive on (Monday/Wednesday/Friday) | `crates/voi_core/src/schedule.rs:14-18` |

### Belief / particle filter

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Belief lot count | $L$ | 50 | lots | Virtual lot slots tracked in the flattened belief | `crates/voi_core/src/params.rs:7` ([`DEFAULT_L_DIM`](/api/rust/voi_core/params/constant.DEFAULT_L_DIM.html)); `crates/voi_core/src/session.rs:238` |
| Belief histogram bins | $K$ | 30 | bins | Freshness histogram bins per lot slot | `crates/voi_core/src/session.rs:239` (studio session default); `crates/voi_core/src/session.rs:1737` (RPC default) |
| Particle count | $N$ | 200 | particles | Particles in the unit-level particle filter's belief bank — each particle is one complete, self-consistent hypothesis about every unit's freshness | Studio (TS) `web/src/controls.ts:140`; RPC default `crates/voi_core/src/session.rs:1566` |

### Control / ordering

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Service quantile | $\alpha$ | 0.9 | probability | Target service fractile for the base-stock order-up-to level | `crates/voi_core/src/session.rs:1032` (`act` RPC fallback); Studio (TS) tunes this per observation scenario with Bayesian Optimization (BO) via `web/src/perChannelTuning.ts:33` (`tunedControllerFor`), rather than using a flat constant — for the scan-waste scenario (`upc\|on\|none`), the optimizer converged to $\alpha\approx0.790$ |
| Damping | $\rho$ | 0.8 | — | Smooths day-to-day changes in the survival-weighted order quantity; this is the default before tuning | `crates/voi_core/src/session.rs:1033` (`act` RPC fallback); Studio (TS) tunes this per observation scenario with BO via `web/src/perChannelTuning.ts:33` (`tunedControllerFor`) — for the scan-waste scenario (`upc\|on\|none`), the optimizer converged to $\rho\approx1.251$, distinct from the $\rho=0.8$ default shown here |
| Rollout horizon | $H$ | 7 | days | Look-ahead length for the rollout controller's forward simulation | `crates/voi_core/src/session.rs:226`; Studio (TS) `web/src/controls.ts:137` |
| Rollout paths | — | 2 | paths | Common random numbers (CRN) sample paths per candidate order evaluated in rollout — the same underlying random draws are reused across candidates so only the order quantity being tested differs | `crates/voi_core/src/session.rs:227`; Studio (TS) `web/src/controls.ts:138` |
| Candidate case radius | — | 1 | cases | Case-steps above/below the base order the rollout search considers | `crates/voi_core/src/session.rs:228`; Studio (TS) `web/src/controls.ts:139` |
| Protection-demand Monte Carlo sample count | $n_\text{mc}$ | 20,000 | samples | Random-sample draws for the heterogeneous protection-period demand quantile | `crates/voi_core/src/policy.rs:13` |

### Economics (studio)

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Sell price | $p_\text{sell}$ | \$4.50 | \$/unit | Studio revenue per unit sold | Studio (TS) `web/src/mock/generate.ts:21` |
| Unit cost | $c_\text{unit}$ | \$1.80 | \$/unit | Studio purchase cost per unit | Studio (TS) `web/src/mock/generate.ts:22` |
| Waste cost | $c_\text{waste}$ | \$1.20 | \$/unit | Studio cost per unit wasted | Studio (TS) `web/src/mock/generate.ts:23` |
| Stockout cost | $c_\text{stockout}$ | \$2.50 | \$/unit | Studio penalty per unit of unmet demand | Studio (TS) `web/src/mock/generate.ts:24` |
| Rollout margin / waste / stockout costs | — | 2.0 / 1.5 / 3.0 | \$/unit | *Separate* internal costs used only by the Rust rollout controller's own look-ahead objective — not the studio profit and loss (P&L) figures above | `crates/voi_core/src/rollout.rs:27-41` ([`RolloutCosts::default`](/api/rust/voi_core/rollout/struct.RolloutCosts.html#method.default)) |

### Episode / studio session

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Episode horizon | — | 90 | days | Length of one studio episode | `crates/voi_core/src/session.rs:632-633`; Studio (TS) `web/src/mock/generate.ts:49` (`window_days`) |
| Default corridor | — | `abdella_mix` | corridor key | Default arrival corridor (lane) selected | `crates/voi_core/src/arrival.rs:23` ([`DEFAULT_ARRIVAL_CORRIDOR`](/api/rust/voi_core/arrival/constant.DEFAULT_ARRIVAL_CORRIDOR.html)); `crates/voi_core/src/params.rs:80` (`arrival_product` default) |

### Arrival-model artifact (`data/abdella/arrival_model.json`, schema 3)

| Parameter | Symbol | Default | Unit | Meaning | Defined in |
| --- | --- | --- | --- | --- | --- |
| Transit legs | $w_k$, $\mu_k$ | 15% / 60% / 25% at 0.35 / 2.58 / 4.32 °C | — / °C | Deterministic break-free baseline (`precool_staging`, `line_haul`, `dock_receiving`); anchored to compressed Abdella-shipment temperatures under a unified $\eta_\text{ref}$ and $q_{10}$ | `data/abdella/arrival_model.json` (`legs`); `crates/voi_core/src/arrival.rs:235` (`legs` on [`ArrivalModel`](/api/rust/voi_core/arrival/struct.ArrivalModel.html)) |
| Reference life (arrival) | $\eta_{\text{ref,arrival}}$ | 14.0 | reference-days | Unified with in-store $\eta_\text{ref}$; the studio's $\eta_\text{ref}$ slider drives both clocks; $k\theta\eta=1$ | `data/abdella/arrival_model.json` (`reference_life_days`); synced via RPC configure and [`sync_params`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.sync_params) |
| Q10 coefficient (arrival) | $Q_{10}$ | 2.0 | ×/10°C | Shared thermal scale for transit exposure and in-store aging; mirrored from studio `q10` via [`sync_params`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.sync_params) | `data/abdella/arrival_model.json` (`q10`); `crates/voi_core/src/params.rs:68` |
| Break temperature | $T_{\mathrm{break}}$ | 12.0 | °C | Fixed temperature during a cold-chain break episode | `data/abdella/arrival_model.json`; `crates/voi_core/src/arrival.rs:242` (`t_break`) |
| Break hazard | $\rho$ | 0.08 | /day | Rate of break events per transit-day (assumed, not fit) | `data/abdella/arrival_model.json`; `crates/voi_core/src/arrival.rs:245` (`rho`) |
| Mean break duration | $\bar\tau$ | 0.5 | days | Mean duration of each break at $T_{\mathrm{break}}$ (assumed) | `data/abdella/arrival_model.json`; `crates/voi_core/src/arrival.rs:248` (`tau_bar`) |
| Position spread | $\sigma_\text{pos}$ | 0.08 | log-scale | Log-normal spread of $\psi$, the inter-lot position noise multiplier — reflecting that a lot's units don't all arrive at exactly the same freshness | `data/abdella/arrival_model.json`; `crates/voi_core/src/arrival.rs:251` (`sigma_pos`) |
| Filter thermal nodes | — | — | — | Stage-gamma baseline nodes used by the filter's numerical integration | `crates/voi_core/src/arrival.rs:1633` (`thermal_nodes_for_key`) |
| Truth transit trace | — | — | — | Bottom-up generative temperature path | `crates/voi_core/src/shipments.rs:98` ([`truth_transit_trace`](/api/rust/voi_core/shipments/fn.truth_transit_trace.html)) |
| Default mixture (`abdella_mix`) | 0.627 × `short_haul` + 0.373 × `long_haul` | — | — | Production default; categorical route-type draw before duration | `data/abdella/arrival_model.json` (`corridor_mixtures.abdella_mix`) |
| Pooled `abdella_all` | $d_\text{min}$ / delay shape / delay scale | 1.853 days / 3.009 / 0.974 | days / — / days | Moment-matched duration law fit across all six Abdella shipments pooled together | `data/abdella/arrival_model.json` (`corridors.abdella_all`) |
| Component `short_haul` | $d_\text{min}$ / shape / scale | 1.803 / 2.0 / 0.05 | days | Duration family fit to one of the six Abdella shipments (labeled S2) | `data/abdella/arrival_model.json` (`corridors.short_haul`) |
| Component `long_haul` | $d_\text{min}$ / shape / scale | 4.033 / 1.628 / 0.814 | days | Duration family fit to four of the six Abdella shipments (labeled S1, S3–S6) | `data/abdella/arrival_model.json` (`corridors.long_haul`) |

## Caveats

- This table lists **defaults** — nearly every physics and demand parameter is exposed as a
  studio slider and can be changed at runtime; a session's actual parameters may differ from
  what's shown here.
- `web/src/mock/generate.ts` (the browser-side mock/demo aging path, separate from the live
  Rust/WebAssembly engine) hard-codes `GAMMA_SCALE = 0.08` (`web/src/mock/generate.ts:29`). The
  canonical value, derived in Rust from `eta_ref` and `gamma_shape`, is
  $1/28\approx0.035714$. Anything computed through that mock path will not match the live
  engine's shelf-life calibration.
- `abdella_mix` (62.7% `short_haul` route + 37.3% `long_haul` route) is the production default
  corridor; `abdella_all` remains the separate, moment-matched fit pooled across all six
  Abdella shipments. In the current studio interface, corridors are selected by name (such as
  `abdella_mix`); the underlying short-haul/long-haul route split is not separately exposed as
  its own pair of selectable arrival lanes.
- Break parameters $\rho$, $\bar\tau$, and $T_{\mathrm{break}}$ are **assumed scenario
  knobs** — the six Abdella shipments are clean chains with no observed breaks, so these three
  can't be fit from that data. Corridor durations, by contrast, are fit to the data; leg
  setpoints are anchored to the break-free temperature centre; $\sigma_\text{pos}$ remains a
  documented adjustment knob rather than a fitted value.
- The retired truncated-normal transit-temperature fields (`mu_T`, `sigma_T`, `temp_floor_c`)
  — originally specified under design record ADR 0148, since superseded by ADR 0150 for the
  transit-temperature approach specifically (ADR 0148's duration-fitting work is still current)
  — have been replaced by the legged baseline plus break-episode model described above and are
  no longer used.
- Control damping uses a parameter also named `rho` in `session.rs` — this is unrelated to the
  break hazard $\rho$ in the arrival artifact; the two happen to share a symbol, not a meaning.
- Rollout's internal look-ahead costs (margin/waste/stockout = 2.0/1.5/3.0, `RolloutCosts`) are
  a *separate* set of numbers from the studio profit and loss (P&L) economics
  ($p_\text{sell}$/$c_\text{unit}$/$c_\text{waste}$/$c_\text{stockout}$) — changing one does not
  change the other, and conflating them will misread what the rollout controller is actually
  optimizing against.

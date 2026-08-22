# 0144. f-native hierarchical arrival model on a shape-scaled gamma with a single reference life

STATUS: PROPOSED
DATE: 2026-08-22
BOARD-ID: MOD-11 / MOD-18 / MOD-19 / FIL
GROUP: MOD
TIER: 1
TICKET: T-150
SUPERSEDES: [0138](./0138-arrival-f-birth-wiring.md) (receipt-tuple birth wiring,
`age_at_receipt` F2 Dirac), [0141](./0141-unified-gamma-arrival-model.md) (Stage C
gamma-in-warped-time with fleet φ̄ bootstrap)
RELATED: [0017](./0017-scn-f2-sunrise-full-age-at-receipt.md) (age-at-receipt rung —
already dead in code, see §Decision 7), [0024](./0024-mod-02-effective-age-dynamics.md),
[0026](./0026-mod-04-spoilage-law.md), [0033](./0033-mod-11-arrival-age-distribution.md),
[0040](./0040-mod-18-transit-model-parameterisation.md),
[0041](./0041-mod-19-t-ref-convention.md) (T_ref = 0 °C, one absolute scale),
[0043](./0043-mod-21-abdella-transit-sampling-frame.md),
[0126](./0126-wasm-rich-filterobs-particle-belief.md) (channel model that superseded 0017),
[0130](./0130-f-native-c2-a-unit-pf.md) (f-native truth and filter),
[0131](./0131-f-native-wire-tau-retirement.md), [0133](./0133-observation-channel-toggles.md),
[0139](./0139-heterogeneous-arrivals-within-lot-dispersion.md),
[0143](./0143-independent-per-unit-gamma-aging.md) (`GammaDecrementTable`, per-unit aging),
[0115](./0115-freshnet-derived-demand-product.md) (committed-artifact precedent)

## Context

Arrival freshness is the input the whole knowledge ladder is supposed to be uncertain about,
and today it is neither uncertain nor correct.

**1. The gamma draw is a freshness loss on one path and an age in days on the other.**
`apply_gamma_decrement` (`crates/voi_core/src/physics.rs:36-47`) subtracts the daily gamma draw
directly from `f`. `birth_f_units_gamma` (`crates/voi_core/src/shipments.rs:87-101`) takes the
*same* draw and feeds it through `age_to_f(·, eta_ref)`, dividing it by 14. Transit degradation
is therefore 14× too cheap wherever Λ is a genuine cumulative exposure — the pack-date and
temperature-history branches of `delivery_birth_f` (`shipments.rs:227-231`) and
`resolve_arrival_lambda` (`unit_pf.rs:289-309`). The P0/P1 default branch is confused twice
rather than once: `day_step.rs:270-277` reconstructs `delivery_lambda` by inverting through
`f_to_age` and then dividing by `k·θ`, which inflates Λ by `1/(k·θ) = 6.25` before the 14×
division, netting out at ≈2.24× too cheap. Both are wrong; the sizes differ by branch.

**2. The ladder is degenerate.** `arrival_product` never reaches Rust (`parse_shipments_from_rpc`,
`session.rs:946-980`, reads only explicit `shipments` / `times` / `temps` arrays), so the fleet
collapses to a single trace and P1/F1/F2a/F2/F3 produce bit-identical beliefs. The guards that
caught this were removed in `bc26218` (three assertions in `session.rs` tests).

**3. Two gamma conventions coexist and cannot be reconciled.** Arrival scales the *shape*,
`Gamma(k·Λ, θ)`. In-store aging scales the *scale*, `Gamma(k, θ·φ)` once per day
(`physics.rs:42-47`, `gamma_decrement_scale` at `:50`). They agree on the mean and disagree on
the spread, and the disagreement is not cosmetic: it decides whether Λ summarizes a journey.

**4. Total shelf life is asserted twice, with different answers.** `ModelParams::default()`
(`params.rs:32-51`) carries `eta_ref = 14.0` days at `t_ref_c = 0.0` — ADR 0041 adopted
`T_ref = 0 °C` precisely so that "transit and in-store AF share one absolute scale" and
"η_ref = 14 d can be quoted at face value". It *also* carries `gamma_shape = 2.0`,
`gamma_scale = 0.08`, and under the production gamma law expected freshness reaches zero at
`1/(k·θ) = 6.25` reference-days. Nothing in the repo reconciles 14 with 6.25; the numbers were
introduced in different milestones and never met. Once `eta_ref` leaves the production path
(this ticket), `1/(k·θ)` silently *becomes* the shelf life, so the contradiction has to be
settled here rather than inherited.

**5. `age_at_receipt` is a rung that no longer exists.** `mask_from_channels`
(`obs.rs:216-243`) never sets it under any `DeliveryHistory` level; Python's `_SCENARIO_PRESENT`
(`src/blueberries_voi/filter/types.py:41-90`) never lists it for any preset; the Rust tests
assert `!age_at_receipt` across all twelve channel combinations and all seven presets. ADR
0126's global-scan channel model superseded ADR 0017's measured-age rung and the field outlived
it, carrying the `eta_ref` division with it.

**6. The frontend is a mock.** `web/src/charts/arrivalPrior.ts` plots
`arrivalFreshnessPriorPdf()` from `web/src/mock/generate.ts` off a hardcoded `ABDELLA_AGES_BASE`.
`spread_scale`, `sensor_sigma` and `transit_temp_bias_c` are studio knobs the engine never reads.

## Decision

### 1. Shape-scaling everywhere

The daily in-store law becomes `Gamma(k·φ, θ)` and the arrival law stays `Gamma(k·Λ, θ)`. Both
are the same gamma process observed over different amounts of warped time.

The physical question is whether warming fruit produces *more* degradation events or *bigger*
ones. Arrhenius describes a rate constant — the frequency with which molecules cross the
activation barrier — so heat means more events of unchanged size: mean and variance both scale
by `φ`, and relative uncertainty falls with temperature. Scale-scaling asserts the same number
of events each `φ` times larger, so variance scales by `φ²` and relative uncertainty is
temperature-invariant. That is the wrong reading of Q10, and it contradicts the premise of
accelerated shelf-life testing, which assumes heat compresses the timeline along the same
trajectory.

Two structural consequences matter more than the physics argument:

- **Λ is a sufficient statistic only under shape-scaling.** `Λ = ∫ q10^((T(t)−T_ref)/10) dt` is
  the journey's cumulative thermal exposure in reference-days. Under scale-scaling, two journeys
  with equal Λ but different temperature paths have equal means and different variances, so Λ
  stops summarizing the trip and F3's inference ("I read the log, therefore I know the arrival
  distribution") becomes invalid — the whole temperature path would have to enter the state.
- **Only shape-scaling is timestep-invariant.** Gamma processes are infinitely divisible, so
  transit as one continuous Λ and the shelf as a daily loop are the same process at different
  temperatures. Under scale-scaling the accumulated variance depends on the discretization,
  which is why the two paths in this repo cannot currently be reconciled at all.

Scale-scaling would be correct only if heat raised event *severity* rather than frequency —
true of chilling and freeze injury, which are threshold effects Q10 does not describe and which
would belong in a separate term if we ever model them.

**Honest caveat.** The gamma process is itself an idealization for berries. Real loss is partly
discrete: a bruise, or mould spreading from one fruit to its neighbours, is better described by
compound Poisson or contagion dynamics than by a continuous subordinator. Shape-scaling is the
more defensible of the two conventions available to us, not a claim of physical exactness.

### 2. One reference life: `k · θ · η_ref = 1`, and `gamma_scale` is recalibrated

We adopt **η_ref = 14 reference-days at T_ref = 0 °C** as the single reference shelf life for
both laws, and derive `gamma_scale` from it:

```
gamma_shape k  = 2.0            (unchanged)
gamma_scale θ  = 1 / (k · η_ref) = 1/28 ≈ 0.035714    (was 0.08)
mean loss      = k·θ = 1/14 ≈ 0.0714 per reference-day
```

`ModelParams` gains one derivation choke point (`set_reference_life` / equivalent) used by
`Default` and by `apply_rpc_configure` when `eta_ref` is supplied without an explicit
`gamma_scale`; an explicit `gamma_scale` still wins for research. A guard test asserts the
default satisfies the invariant.

Why recalibrate rather than keep `k·θ = 0.16` and accept a large spoiled-on-arrival atom:

- Refrigerated-leg exposure over the six Abdella corridors is roughly `Λ ∈ [2.6, 8.8]`
  reference-days (durations ≈1.9–6.5 d at lot-mean ≈2.7 °C, `φ̄ = 3^0.27 ≈ 1.35`). Against a
  6.25-reference-day life, expected loss on the four longest corridors exceeds 1.0 and the exact
  atom `P(f = 0 | Λ) = Q(kΛ, 1/θ)` reaches ≈0.9 on the longest. Five of six corridors would
  deliver fruit that is mostly dead on arrival. A store with nothing to sell is not a simulation
  of a store, and a ladder whose every rung agrees "it is spoiled" carries no information.
- ADR 0041 already committed to η_ref = 14 d at 0 °C being quotable at face value and to transit
  and in-store aging sharing one absolute scale. `k·θ = 0.16` silently violated that; honoring it
  is the smaller change to the repo's stated position, not the larger one.
- 14 days at 0 °C is the literature-defensible number for blueberries; 6.25 is not.
- Store-side dynamics barely move, because arrival freshness absorbs the difference. Today:
  arrival `f ≈ 0.97`, daily loss at 4 °C `= 0.248`, ≈3.9 days on display. After: arrival
  `f ≈ 0.54` (fleet mean), daily loss at 4 °C `= 0.111`, ≈4.9 days on display. Waste cadence
  survives; what changes is that arrival freshness becomes *uncertain and consequential*, which
  is the point of the ticket.

Under the new calibration, arrival freshness by corridor is roughly `f ∈ [0.37, 0.82]` with the
`f = 0` atom ≈1% on the longest corridor — a spread the ladder can actually learn about, rather
than a point mass at 0.97 or a point mass at 0. The exact figures are the calibration note's job
to publish, not this ADR's; the numbers here are order-of-magnitude justification.

Note on the convention: `1/(k·θ)` is the exposure at which *expected* freshness reaches zero,
whereas Weibull `η_ref` is the characteristic life (`S = e⁻¹`). These are different quantiles of
different laws — Weibull mean life at `β = 2` is `η·Γ(1.5) ≈ 0.886 η`. Equating them is a
calibration convention that removes a contradiction, not a claim that the two laws coincide.

### 3. Hierarchical arrival model in f-space, from assumed families

Arrival freshness is generated in f-space, with no age round trip:

```
corridor          → d_min, delay params        modeled input, keyed by arrival_product
d       = d_min + Gamma(a_d, b_d)              transit floor plus accumulated delay
T_bar   ~ TruncNormal(mu_T, sigma_T, low=0C)   reefer setpoint with imperfect control
phi_bar = q10^((T_bar - T_ref)/10)             Arrhenius; parameter stays in Celsius
psi_pos ~ Lognormal(0, sigma_pos)              position within pallet, drawn PER UNIT
Lambda  = d * phi_bar * psi_pos
D       ~ Gamma(k * Lambda, theta)             per-unit, in warped time
f       = max(0, 1 - D)
```

Closed form, no new numerics: `P(f > x | Λ) = gamma_p(kΛ, (1−x)/θ)` and the atom
`P(f = 0 | Λ) = gamma_q(kΛ, 1/θ)`, both from the existing `physics.rs` helpers. Unobserved
levels are integrated by deterministic quadrature over `(d, T_bar)`.

**These are assumed families, roughly calibrated — not fits.** With `n = 6` shipments an MLE
invites over-reading. `data/abdella/arrival_model.json` is hand-authored with round,
interpretable parameters chosen to bracket the observed values, carries a schema version, and is
embedded in Rust exactly once via a single accessor. `scripts/arrival_calibration_note.py`
*reports*: it overlays each assumed curve on the six observed points and states plainly that the
data does not validate them. It contains no fitting step. Two suspect probes (S4 has a position
at `φ̄ = 4.73`, implying ~14 °C sustained against a lot-mean max of 8.7 °C) are named in the
note and excluded from the `sigma_pos` calibration rather than screened by a rule.

Family choices: shifted gamma on duration (hard floor at the corridor minimum, right tail
because delays only add, stays in the gamma family for clean composition); truncated normal on
mean transit temperature with `φ̄` derived (keeps the parameter arguable by a domain expert,
gets the Q10 nonlinearity for free, makes the freeze floor a natural truncation); small
lognormal on position (bounded multiplicative penalty relative to the coldest spot, right tail
for hot corners). Within-trip fluctuation contributes ≤4% to `φ̄` across all six traces, so the
Jensen correction is ignored and documented rather than parameterized. Duration accounts for
≈98.4% of `Var(log Λ)` between shipments, which is why duration is an explicit modeled corridor
input rather than something inferred from six numbers.

### 4. Scope: refrigerated leg only, single segment

The harvest-to-precool field-heat window stays out, matching current trace processing. Two
consequences must be stated in the ADR, the spec, and the calibration note:

- **Pack date is the only date rung.** Harvest date is not modeled and would buy nothing,
  because the segment that would distinguish it is absent.
- **Arrival freshness is an upper bound.** Field heat is the most thermally damaging segment of
  the chain, so real arrival freshness sits below what this model reports.
  `data/abdella/PROVENANCE.md:25-28` excluded it only to keep τ inside the now-retired FIL-15
  `[0, 8]` grid. That reason is gone, so this is now a deliberate scope choice worth revisiting
  in a later ticket — not something silently inherited.

`d` and `φ̄` must be measured over the *same* window; the calibration note verifies this before
the artifact is committed. Multiplying a harvest-inclusive `d` by a refrigerated-leg `φ̄` would
understate degradation.

### 5. No observation channel ever reveals freshness

A date reveals a *calendar duration*. Freshness is derived by combining that duration with the
modeled temperature distribution, which yields a **distribution** over `f`. That distribution,
not a scalar, is what seeds the lot. This is the invariant the remodel exists to enforce, and it
determines the conditional structure of the artifact — which must be a joint law, not a
marginal, or the flat-ladder bug is baked in permanently:

| Rung | Conditions on | Integrates over |
| --- | --- | --- |
| F3 (temperature history) | `T_bar`, hence `φ̄` | `d` if unobserved, `ψ_pos`, gamma |
| F2 / F2a (pack date) | `d` only | `T_bar`, `ψ_pos`, gamma |
| P0 / P1 | nothing | `d`, `T_bar`, `ψ_pos`, gamma |

No rung ever sees `ψ_pos` or the per-unit gamma draw. That is the belief-sharpness floor and the
reason units within one lot arrive with genuinely different freshness. `FilterObs` carries no
freshness-valued arrival field; a date can only enter as a duration.

### 6. Terminology: "effective age" retired in the UI and live code

Freshness is the state variable. Λ is a property of the *journey*, not of the fruit, so it is
named **cumulative thermal exposure** in reference-days (short: `exposure`) — a dose that drives
loss, never an age the product carries.

Scope is the UI and the live implementation only. Historical ADRs (0017, 0018, 0024, 0026, 0027,
0040, 0041, 0046, 0078, 0105 and others), `.team/` records, notebooks and `experiments/` keep
their language as records of decisions made at the time. **This ADR notes the retirement; it
does not rewrite them.** `age_to_f` / `f_to_age` and their `eta_ref` scaling survive under their
current names for the legacy Weibull research path (`rollout.rs:74,88`), off the production hot
path, so legacy goldens stay readable; only their doc comments gain exposure language. The
Python legacy filter and simulator (`src/blueberries_voi/filter/`, `src/blueberries_voi/sim/`)
are research paths under ADR 0130 and keep `age_at_receipt` as-is; the grep guards allowlist
them explicitly.

### 7. Delete the dead `age_at_receipt` rung and its two f-scalar helpers

`ObsMask::age_at_receipt`, `RichDay::age_at_receipt`, `FilterObs::age_at_receipt` and the
`age_at_receipt` arm of `ObsMask::apply` are deleted from the Rust live path, together with
`shipments::f_at_receipt_from_age` and `shipments::birth_f_f2_dirac` — the latter two *are* the
`eta_ref` division, and `birth_f_f2_dirac` is a literal point mass on freshness, which §5
forbids. The corresponding TypeScript fields go with them. ADR 0017's measured-age rung was
already superseded in substance by ADR 0126's channel model; this records that the field is now
gone in fact as well.

### 8. Add no new runtime dependencies

The artifact is JSON parsed with the existing serde stack; quadrature nodes and weights are
deterministic and version-pinned inside the artifact so Python/Rust parity cannot drift for
reasons unrelated to the model.

## Alternatives considered

- **Keep scale-scaling in store and shape-scaling at arrival (status quo)** — rejected: the two
  are different processes, Λ stops being sufficient, F3's inference is invalid, and accumulated
  variance depends on the shelf timestep.
- **Scale-scaling everywhere** — rejected: makes relative uncertainty temperature-invariant,
  which misreads Q10 as event severity rather than event frequency, and destroys Λ sufficiency.
- **Separate gamma rates for transit and shelf** — rejected: this is exactly the
  non-unification the ticket removes; it would let the 6.25-vs-14 contradiction survive under a
  new name.
- **Keep `k·θ = 0.16` and accept the spoiled-on-arrival atom** — rejected: `P(f = 0)` ≈ 0.9 on
  the longest corridor, five of six corridors mostly dead on arrival, no information left for
  any rung to buy, and a direct contradiction of ADR 0041.
- **Re-anchor `T_ref` to display temperature so `φ̄` shrinks** — rejected: ADR 0041 settled
  `T_ref = 0 °C` deliberately, and rescaling the clock to make an over-aggressive `k·θ` look
  reasonable hides the calibration error instead of fixing it.
- **Fit the arrival families by MLE against the six traces** — rejected: `n = 6`; a fit would be
  read as validation the data cannot support. Hand-authored round parameters plus an honest
  reporting note say the same thing without the false precision.
- **Include the harvest-to-precool field-heat window** — rejected *for this ticket*: it needs its
  own segment, its own data treatment, and a harvest-date rung. Recorded as a known upper-bound
  bias with a follow-up ticket rather than done badly here.
- **Keep `age_at_receipt` as a latent rung for a future sensor** — rejected: it is unreachable
  under ADR 0126 channels, and keeping it means keeping a freshness-valued observation field,
  which §5 forbids outright.
- **Rewrite the historical ADRs to the new vocabulary** — rejected: they are records of what was
  decided when, not documentation of current behavior.

## Consequences

**Makes easy.** One gamma process from transit through display, so a shelf-day and a transit-day
at the same temperature cost the same freshness and can be tested against each other. Λ becomes
a genuine sufficient statistic, so F3 is an `O(1)` lookup instead of per-particle path
integration and the wire stops carrying full traces. Each rung conditions on exactly what it
observes, so the monotone ladder `Var(f | φ̄) ≤ Var(f | d) ≤ Var(f)` is a testable property
rather than an aspiration. The `f = 0` atom is available in closed form as a headline number.

**Makes hard / costs.** Recalibrating `gamma_scale` moves every store-side number: waste rates,
α tuning, VOI CRN snapshots, and the conclusions in notebooks 13 and 14. Arrival freshness moves
from ≈0.97 to ≈0.54 and becomes a per-unit distribution rather than one scalar per delivery.
Shelf-side daily spread tightens ≈20% from shape-scaling alone at fixed `k·θ` (sd 0.176 → 0.141
at 4 °C, means unchanged) before the recalibration changes the level. The ladder's shape changes:
P1 → F2 becomes a large gain because duration is ≈98% of lot-mean uncertainty, F2 → F3 a smaller
one that pays in tail risk rather than in the mean. Both notebooks need re-running and their
narratives revisited — CRN is not comparable across this physics epoch.

**Locks in.** Shape-scaling as the single gamma convention; `k·θ·η_ref = 1` as the calibration
invariant; the arrival artifact as a schema-versioned committed joint law embedded once;
`FilterObs` carrying no freshness-valued arrival field; the refrigerated leg as the modeled
span, with arrival freshness explicitly an upper bound.

**Revisit if.** Field heat is brought into scope (needs a second segment, a harvest-date rung,
and its own ADR); or discrete loss mechanisms (bruising, mould contagion) are shown to dominate,
in which case the gamma subordinator itself — not just its scaling convention — is the thing to
replace; or a real fit becomes possible with substantially more than six shipments.

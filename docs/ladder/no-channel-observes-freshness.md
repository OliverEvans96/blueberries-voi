---
title: No channel observes freshness
sources:
  adr: [0144]
  code:
    [
      crates/voi_core/src/arrival.rs,
      crates/voi_core/src/unit_pf.rs,
      crates/voi_core/src/obs.rs,
      crates/voi_core/src/physics.rs,
    ]
---

# No channel ever observes freshness

Even the richest rung on the [ladder](./rungs.md) — a full temperature-history trace read
off a logger that rode with the pallet — never hands the filter a freshness number. It
hands a *duration* or a *heat integral*. Freshness itself, `f`, depends on things no
sensor in this model reads: exactly where a unit sat inside the pallet, and how that
particular unit's own spoilage happened to run. This page is the reason `FilterObs` (the
struct every observation channel ultimately fills in) has no freshness-valued field at
all — there is nothing in the wire format for it to fill.

> **Figure (coming soon):** the three-tier conditioning diagram from ADR 0144 §5 —
> corridor → duration `d` → temperature factor `φ̄` → cumulative exposure `Λ`, with the
> three rungs (P0/P1, F2/F2a, F3) marked at the level each one conditions on, and the
> remaining hidden variables (`ψ`, the per-unit gamma draw) shown as always-unresolved
> beneath every rung. (An older `marginal_snapshot_p0_vs_f2.png` exists in the repo's
> figure archive but labels its F2 panel "age at receipt," the terminology this project
> retired — it is not used here.)

## The idea

Picture a pallet of blueberries leaving the farm. Two different instruments could ride
along with it:

- A **pack-date stamp** tells you when the pallet was packed. Compared against today's
  date, that's a *calendar duration* — five days, say. It says nothing about how cold the
  truck actually ran.
- A **temperature logger** tells you the truck's temperature at every point along the
  route. Integrated over the trip, that's a *cumulative thermal exposure* — a single
  number that combines how long the trip took **and** how much heat stress it involved.

Neither one is a freshness reading. A five-day trip in a well-run reefer barely stresses
the fruit; a five-day trip with the compressor cycling badly can spoil it outright. So
even after you observe the pack date (or the full temperature trace), you still don't
know the fruit's freshness — you know one input to it, and you're left holding a
*distribution* over freshness that reflects everything else you still don't know:
exactly how cold the truck ran on average, and, because a pallet isn't a single
temperature, where inside it any given unit happened to sit. Combine what you did
observe with the model's prior over everything you didn't, and you get a spread of
plausible freshness values — never a single point.

That's also why upgrading the delivery-history channel (P0/P1 → F2/F2a → F3) narrows
this spread rather than replacing a guess with a fact. F3 pins down the most about the
journey, but it still can't tell you which units in the pallet sat in the coldest corner
versus the warmest, or which units happened to spoil a little faster than their
neighbors for reasons no sensor tracks.

## The math

The arrival model (ADR 0144 §3) generates a unit's freshness through a short chain of
unobserved and partly-observed quantities:

- $d$ — the **calendar transit duration** in days: time from pack to arrival.
- $\bar T$ — the shipment's mean transit temperature, and $\bar\phi$ (`phi_bar`) — the
  corresponding **duration-averaged Q10 temperature factor**,
  $\bar\phi = q_{10}^{(\bar T - T_{\text{ref}})/10}$, where $q_{10}$ is the multiplicative
  factor a 10 °C rise applies to spoilage rate and $T_{\text{ref}}$ is the reference
  temperature.
- $\psi$ (`psi`) — a **within-pallet position multiplier**, drawn independently per unit,
  capturing that a unit in the coldest corner of the pallet ages slower than one in the
  warmest.
- $\Lambda$ (`Lambda`) — the **cumulative thermal exposure**, in reference-days:
  $$
  \Lambda = d \cdot \bar\phi \cdot \psi.
  $$
  $\Lambda$ is a property of the *journey a unit took*, never something the fruit itself
  carries.
- A per-unit gamma draw converts $\Lambda$ into freshness: $f = \max(0, 1 - D)$ where $D
  \sim \mathrm{Gamma}(k \Lambda, \theta)$, so
  $$
  P(f > x \mid \Lambda) = \gamma_p(k \Lambda, (1-x)/\theta), \qquad
  P(f = 0 \mid \Lambda) = \gamma_q(k \Lambda, 1/\theta),
  $$
  using the regularized incomplete gamma functions $\gamma_p$ and $\gamma_q$.

No observation channel ever reports $f$, $\psi$, or the per-unit gamma draw directly.
What a channel reports determines how much of this chain gets pinned down before the
remaining pieces are integrated out:

| Rung | Observes | Conditions on | Integrates over |
| --- | --- | --- | --- |
| F3 (temperature history) | the full trace — timestamps **and** temperatures | $\Lambda$ (both $d$ and $\bar\phi$ together) | $\psi$, the per-unit gamma draw |
| F2 / F2a (pack date) | pack date | $d$ only | $\bar T$ (hence $\bar\phi$), $\psi$, the per-unit gamma draw |
| P0 / P1 (no delivery history) | nothing about the delivery | the corridor configuration only | $d$, $\bar T$, $\psi$, the per-unit gamma draw |

Whatever is "integrated over" in that table is exactly the source of the residual spread
described in the intuition above — it is not approximation error, it is the honest
consequence of a variable no rung ever measures.

## Why it's modelled this way

ADR 0144 §5 states the invariant this page documents directly: "A date reveals a
*calendar duration*. Freshness is derived by combining that duration with the modeled
temperature distribution, which yields a **distribution** over `f`. That distribution,
not a scalar, is what seeds the lot." The ADR calls this "the invariant the remodel
exists to enforce" — earlier code let a delivery observation collapse straight to a
single freshness number (a *point mass*), which silently threw away real uncertainty and
produced a "flat-ladder bug": every rung would end up producing statistically
indistinguishable beliefs, because the one place where richer information should have
sharpened the belief was instead discarded at the conversion step.

**Alternative rejected — a direct age/freshness-valued observation field.** An earlier
rung design (ADR 0017, the original SCN-F2 "age at receipt") observed a measured age
directly and converted it to a freshness scalar via `age_to_f`. ADR 0144 §7 deletes this
from the production path outright: `ObsMask::age_at_receipt`, `RichDay::age_at_receipt`,
`FilterObs::age_at_receipt`, and the two f-scalar helpers `f_at_receipt_from_age` and
`birth_f_f2_dirac` are gone from the live Rust path specifically because
`birth_f_f2_dirac` is "a literal point mass on freshness," which §5 forbids. (The
`age_to_f`/`f_to_age` mapping still exists, but only for the retired, non-production
Weibull research path — it is not used by any current rung.)

**Honest caveat, from the ADR's own self-correction.** The conditioning table above was
itself wrong in an earlier draft of ADR 0144: it had F3 conditioning on $\bar T$ alone
and integrating over $d$ "if unobserved," even though the temperature trace F3 actually
receives carries timestamps and therefore reveals $d$ exactly. That understated how much
F3 should know, and the ADR's own "Correction 1" section documents the fix explicitly
rather than quietly editing the number away. The lesson generalizes: getting this
conditioning structure right is easy to get subtly wrong, and this project has already
done so once in a way that would have understated one of its headline results (the
F2→F3 information gain) had it shipped.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Channel-conditional arrival law, mutually exclusive cases | `enum ArrivalCondition { Exposure(f64), Duration(i32), Prior }` | `crates/voi_core/src/arrival.rs:25` |
| F3 case: conditions on the full exposure $\Lambda$ | `ArrivalCondition::Exposure(f64)` | `crates/voi_core/src/arrival.rs:27` |
| F2/F2a case: conditions on duration $d$ only | `ArrivalCondition::Duration(i32)` | `crates/voi_core/src/arrival.rs:29` |
| P0/P1 case: corridor prior only | `ArrivalCondition::Prior` | `crates/voi_core/src/arrival.rs:31` |
| Exact $\Lambda$ from an observed trace (the F3 integral) | `resolve_arrival_exposure(obs_temps, obs_times, q10, t_ref)` | `crates/voi_core/src/arrival.rs:776` |
| $P(f>x \mid \Lambda)$ / $P(f=0 \mid \Lambda)$ | `ArrivalModel::p_f_gt_at`, `ArrivalModel::p_f_zero` | `crates/voi_core/src/arrival.rs:400`, `crates/voi_core/src/arrival.rs:426` |
| $\bar\phi = q_{10}^{(\bar T - T_{\text{ref}})/10}$ | `store_temp_factor(t_store_c, t_ref_c, q10)` | `crates/voi_core/src/physics.rs:31` |
| Filter's own choice of condition, per-day, from `FilterObs` | `resolve_arrival_f_law(obs, params)` | `crates/voi_core/src/unit_pf.rs:287` |
| No freshness-valued field on the wire | `struct FilterObs { .. temp_times_d, temp_temps_c, pack_date_days .. }` (no `f` field) | `crates/voi_core/src/obs.rs:60` |
| Retired age↔freshness mapping (legacy Weibull salvage path only, not a production rung) | `age_to_f`, `f_to_age` | `crates/voi_core/src/physics.rs:15`, `crates/voi_core/src/physics.rs:23` (used at `crates/voi_core/src/rollout.rs:90`) |

## Caveats

- $\psi$ (within-pallet position) and the per-unit gamma draw are **never** observed by
  any rung, including F3. That is a deliberate floor on how sharp belief can ever get —
  ADR 0144 calls it "the belief-sharpness floor and the reason units within one lot
  arrive with genuinely different freshness" — not a gap this project intends to close
  with a richer channel.
- The whole arrival chain models the **refrigerated leg only**. The harvest-to-precool
  field-heat window before refrigeration starts is out of scope, so the freshness this
  model reports at arrival is an upper bound — real arrival freshness is likely somewhat
  lower than what any rung, including F3, would infer.
- The conditional laws ($P(f>x\mid\Lambda)$, the $d$-marginal for F2/F2a) are built from
  **assumed parametric families calibrated by hand against six shipments**, not fit by
  maximum likelihood — ADR 0144 §3 is explicit that six shipments cannot support a fit
  claim. Treat the shape of these distributions as a documented modeling choice, not a
  measured fact about the actual cold chain.

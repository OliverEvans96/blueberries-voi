# 0058. CTL-01: Base policy family
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: CTL-01
GROUP: CTL
PROVENANCE: yours
TIER: 1
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M2. Not on the critical path for the filter, but the first thing that needs an answer
once M1 lands.*

**The question.**

Your own plan says "define a base policy — freshness-adjusted base-stock algorithm." The AI note
([The Controller — Survival-Weighted Base-Stock with
Rollout](../../The%20Controller%20%E2%80%94%20Survival-Weighted%20Base-Stock%20with%20Rollout.md)) fleshes
that out into a specific rule: order enough to cover demand over the protection interval, where "how
much you have" is counted as units *weighted by their probability of still being alive when a
customer wants them* —

$$\tilde I_t=\sum_{\ell\text{ on hand}}w(\tau_\ell)n_\ell+\sum_{j=1}^{L}q_{t-j}\,\mathbb E_g[w_j],\qquad
w(\tau)=\frac{S(\tau+\Delta\tau_L)}{S(\tau)}$$

$$q_t=\text{caseRound}\big([F^{-1}_{D_{t:t+L}}(\alpha)-\tilde I_t]^+\big)$$

This is the base policy that rollout ([CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md)) wraps.
The open question is whether to include the damping correction from the start or treat it as a
tunable extension.

**Why this is the right family, not just a reasonable one.**

Van Zyl / Veinott (1965): under proportional decay (β=1) with **zero lead time**, base-stock policies
are provably optimal. Proportional decay is β=1 here, so the base policy is *exactly optimal* in that
degenerate case, and the two things that break optimality — β≠1 and positive lead time — are exactly
the two things this project is about. That's a clean framing for the post, not just a convenient
heuristic.

**Known defect:** a base-stock policy has ∂q/∂x = −1 exactly; the true optimum satisfies
−1<y'≤0, so the family structurally over-responds to inventory. Nahmias (1975b) found the damped form
performs comparably to the best critical number and should also help under parameter uncertainty —
which is exactly where this family is known to be exposed (see the model-misspecification arm in
[CTL-06](CTL-06%20Optimality%20certificate.md)).

## Decision

We will adopt **C — Damped survival-weighted (Nahmias ρ)**. Chosen against the card recommendation of **B — Survival-weighted base-stock, order quantity only**.

**C — Damped survival-weighted (Nahmias ρ).** ⚑ Against the card's recommendation (B). One extra scalar; q_t = caseRound(ρ[F⁻¹(α) − Ĩ_t]⁺), 0<ρ≤1. Corrects the family's structural over-response (∂q/∂x = −1 exactly, vs optimal −1<y'≤0).

## Alternatives considered

- **A — Plain base-stock, age-blind** — not chosen. Deflates nothing; counts units on hand. The strawman.
- **B — Survival-weighted base-stock, order quantity only** _(card recommendation; not chosen)_ — not chosen. Effective inventory = units weighted by probability of surviving the wait. Your own bullets ("freshness-adjusted base-stock algorithm").

## Consequences

One extra scalar; q_t = caseRound(ρ[F⁻¹(α) − Ĩ_t]⁺), 0<ρ≤1. Corrects the family's structural over-response (∂q/∂x = −1 exactly, vs optimal −1<y'≤0).

**What this gates:** [CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md) rollout wraps whichever base policy is chosen
here. [CTL-05](CTL-05%20Baseline%20ladder.md)'s baseline ladder is built around this rule as "the main
policy." The β=1 degeneracy check in [CTL-06](CTL-06%20Optimality%20certificate.md) is a direct
consequence of this choice.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** The [CTL-06](CTL-06%20Optimality%20certificate.md) optimality-gap certificate comes back large *and*
CRN is confirmed clean — that's the trigger the AI notes name for reaching for damping (C) before
anything more drastic.

**Depends on:** `X-04`, `MOD-07`, `FIL-01`

**Milestone:** M2 — controller and multi-scenario

## Note (2026-08-30): Studio / Ax ρ range widened

The accepted decision above defines **Nahmias damping** semantics: $0<\rho\le 1$ partially closes
the order gap. Studio (`web/src/controls.ts`) and Ax notebook 12 now allow $\rho\in[0.5,2]$ for
**empirical tuning** — values $\rho>1$ over-close the gap (aggressive ordering), not classical
damping. The implementation (`policy.rs`) accepts any $\rho>0$; only the tuning path documents the
widened cap (`alpha_tune.rs`, `MAX_DAMPED_SW_RHO=2`). Default production $\rho=0.8$ remains inside
the Nahmias band unless tuning shows otherwise.

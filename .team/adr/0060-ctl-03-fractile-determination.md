# 0060. CTL-03: Fractile determination
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: CTL-03
GROUP: CTL
PROVENANCE: notes-agree
TIER: 2
MILESTONE: M2 — controller and multi-scenario
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M2.*

**The question.**

$q_t=\text{caseRound}([F^{-1}_{D_{t:t+L}}(\alpha)-\tilde I_t]^+)$ needs an $\alpha$. The textbook
newsvendor fractile $c_s/(c_s+c_w)$ is derived for a single-period problem where leftover stock is
destroyed. That's not this problem — a leftover unit here is usually sold tomorrow, so the true
overage cost is $h+c_w\cdot P(\text{outdates before selling})$, which itself depends on the policy in
a way the closed form doesn't capture.

## Decision

We will adopt **B — Tuned by simulation**. Chosen against the card recommendation of **C — Both, reported side by side**.

**B — Tuned by simulation.** ⚑ Against the card's recommendation (C). Recovers the Nahmias (1976) / Nandakumar & Morton (1993) correction empirically, without deriving it.

## Alternatives considered

- **A — Theoretical newsvendor fractile, c_s/(c_s+c_w)** — not chosen. Wrong here — assumes leftovers are destroyed, but a leftover unit is usually sold tomorrow.
- **C — Both, reported side by side** _(card recommendation; not chosen)_ — not chosen. alpha^theory vs alpha*, gap as a function of beta — a natural small appendix figure.

## Consequences

Recovers the Nahmias (1976) / Nandakumar & Morton (1993) correction empirically, without deriving it.

**What this gates:** Every arm of the VOI sweep needs a tuned $\alpha$, including every baseline
([CTL-05](CTL-05%20Baseline%20ladder.md)) — an untuned Rung 0 is called out in the AI notes as "the
easiest way to manufacture an impressive and worthless number." This decision fixes the standard all
arms are held to.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** Never, in practice — this is a tuning-standard choice, not a modelling one. Revisit only if the
tuning grid search turns out to be a compute bottleneck across the full VOI sweep.

**Depends on:** `CTL-01`, `X-02`

**Milestone:** M2 — controller and multi-scenario

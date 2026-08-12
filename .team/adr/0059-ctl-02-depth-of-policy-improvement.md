# 0059. CTL-02: Depth of policy improvement
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: CTL-02
GROUP: CTL
PROVENANCE: yours
TIER: 1
MILESTONE: M2 — controller and multi-scenario

## Context

*Milestone: M2.*

**The question.**

Your plan already specifies rollout: "for each available action, run base policy over H steps
forward... pick the action with highest expected value." The question the board needs to ratify is
how far to take that idea — none, one step, or more than one — since the AI notes argue this
explicitly rather than assuming it.

$$\tilde\pi(x)=\arg\max_u\ \mathbb E\big[g(x,u,w)+J_\pi(f(x,u,w))\big]$$

$J_\pi$ (expected profit forever under the base policy) can't be written down but can be *sampled*
via the simulator. Rollout is one step of that improvement, done online, discarded after the day's
decision.

**Decision rule if this needs revisiting later.**

| Certificate says | Do |
| --- | --- |
| Gap ≲1%, claimed VOI ~several % | Done — B stands |
| Gap large (~5%) | First suspect CRN desync (looks identical to under-improvement) |
| Still large after CRN check | Try damping ρ in [CTL-01](CTL-01%20Base%20policy%20family.md) — a better base policy raises $J_{\tilde\pi}$ directly, for one scalar |
| Still large, specifically lookahead-depth-limited | Only then consider C |

## Decision

We will adopt **B — Single-step rollout**.

**B — Single-step rollout.** One step of policy iteration, computed online at states you actually visit. Your own bullets describe exactly this.

## Alternatives considered

- **A — Base policy only, no lookahead** — not chosen. Ship CTL-01 as-is. Cheapest; leaves the improvement guarantee on the table.
- **C — Deeper — approximate PI / DCL-style amortised training** — not chosen. Rollout-on-rollout, or train a policy offline on rollout labels (Temizöz et al.). Buys inference-latency, not decision quality, at this scale.

## Consequences

One step of policy iteration, computed online at states you actually visit. Your own bullets describe exactly this.

**What this gates:** The rollout mechanics — common random numbers, horizon and terminal value — are only relevant if B or
C is chosen; see [CTL-04](CTL-04%20Rollout%20horizon%20and%20terminal%20value.md). The certificate in
[CTL-06](CTL-06%20Optimality%20certificate.md) is what adjudicates whether this needs revisiting.

**Revisit if:** The optimality-gap certificate ([CTL-06](CTL-06%20Optimality%20certificate.md)) comes back large after
CRN is confirmed clean and damping (ρ, [CTL-01](CTL-01%20Base%20policy%20family.md)) is already in
play.

**Depends on:** `CTL-01`, `X-06`

**Milestone:** M2 — controller and multi-scenario

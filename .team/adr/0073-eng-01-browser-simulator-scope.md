# 0073. ENG-01: Browser simulator scope
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: contested
TIER: 1
AGAINST-RECOMMENDATION: true

## Context

*Flagged in [Updated Plan — Filter, Controller, and Where the Weibull
Sits](../../Updated%20Plan%20%E2%80%94%20Filter%2C%20Controller%2C%20and%20Where%20the%20Weibull%20Sits.md)
§A.6 as **"highest engineering risk"** of the whole deliverable list.*

**The question.**

Your bullets ask for two different things and it's worth being explicit that they're different:
"simulator should be available as real-time / interactive in browser" (an engineering promise about
what runs client-side) and "interactive visualization / decision tool" (a reader-experience promise
about what the reader can explore). B satisfies the second without attempting the first.

**Why A is not free.**

A $10^4$-particle RBPF plus a rollout controller (§CTL-02's own accounting: ~24k day-steps per
decision, 0.1–0.5s **in Julia/Python**) does not run interactively in a browser tab. Porting the
inference layer to WASM is real engineering — a different language runtime, a different debugging
loop, and no reuse of [X-09](X-09%20Language%20and%20stack.md)'s Python stack — for a payoff (live
inference in front of the reader) that a reader browsing a blog post is unlikely to notice or need.

## Decision

We will adopt **C — No interactive component — static figures only**. Chosen against the card recommendation of **B — JS forward simulator only, pre-baked posteriors and VOI surfaces as JSON**.

**C — No interactive component — static figures only.** ⚑ Against the card's recommendation (B). Cheapest; drops the "interactive visualization / decision tool" idea from your own bullets entirely.

## Alternatives considered

- **A — Full live inference in the browser — WASM port of the filter and rollout** — not chosen. What "real-time / interactive" literally means in your bullets. The AI note calls this a multi-day detour and does not recommend it.
- **B — JS forward simulator only, pre-baked posteriors and VOI surfaces as JSON** _(card recommendation; not chosen)_ — not chosen. Reader drives beta and sigma and watches the shelf; no live inference. The AI note's recommendation.

## Consequences

Cheapest; drops the "interactive visualization / decision tool" idea from your own bullets entirely.

**What this gates:** If B: the JSON export format from the Python VOI sweep becomes a real interface contract, worth
fixing early rather than backfilling. If A: filter and controller code need a second target runtime
from day one, which would push back onto [X-09](X-09%20Language%20and%20stack.md).

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** B's JSON payload turns out too large to ship statically (e.g. the full scenario × β × belief grid),
at which point a lightweight server-side endpoint becomes cheaper than either A or a truncated grid.

**Depends on:** `X-09`, `FIL-01`, `CTL-02`

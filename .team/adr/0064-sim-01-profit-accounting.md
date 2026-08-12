# 0064. SIM-01: Profit accounting
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SIM-01
GROUP: SIM
PROVENANCE: newly-raised
TIER: 1
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

*Flagged as unresolved in [Updated Plan — Filter, Controller, and Where the Weibull
Sits](../../Updated%20Plan%20%E2%80%94%20Filter%2C%20Controller%2C%20and%20Where%20the%20Weibull%20Sits.md)
§C.2: "Cost structure. VOI must be reported in profit, not waste — margin, waste cost, stockout cost,
disposal cost." Nobody has picked among these yet.*

**The question.**

[X-02](X-02%20Objective%20denomination.md) settled that VOI is reported in profit, not units of waste
avoided or forecast error. That doesn't yet say what enters the profit calculation. This is not a
detail — it's the actual number the whole post reports, and the components chosen change *which*
policy comparisons look favorable.

**Why this isn't trivial.**

[MOD-10](MOD-10%20Unmet%20demand.md) already settled that unmet demand is lost sales, censored — no
backorder. A stockout therefore costs at minimum the forgone margin on the lost sale. Whether it costs
*more than that* (a customer who doesn't find blueberries today may buy fewer next time, or shop
elsewhere) is a real modelling choice with real consequences: without a stockout penalty beyond
forgone margin, a policy that runs lean and occasionally stocks out looks better than it should, which
directly works against the case for age information (age-aware policies buy their edge partly by
avoiding both waste *and* stockouts).

[X-12](X-12%20Tripwire%20if%20the%20headline%20number%20is%20flat.md) already commits to a
stockout-penalty sensitivity sweep as the fallback if the headline VOI is flat — that sweep only makes
sense if a stockout penalty is a first-class term in the accounting to begin with, not something bolted
on after the fact.

## Decision

We will adopt **B — Margin, waste cost, and an explicit stockout penalty**.

**B — Margin, waste cost, and an explicit stockout penalty.** Adds a cost per lost sale beyond forgone margin -- e.g. a goodwill/switching term. Matches X-12's stockout-penalty sensitivity sweep.

## Alternatives considered

- **A — Margin and waste cost only** — not chosen. revenue - COGS - disposal cost of spoiled units. Simplest; omits the stockout penalty entirely.
- **C — Full P&L -- margin, waste cost, stockout penalty, and holding cost** — not chosen. Most complete; holding cost is usually small for a fast-turning perishable and may not earn its complexity.

## Consequences

Adds a cost per lost sale beyond forgone margin -- e.g. a goodwill/switching term. Matches X-12's stockout-penalty sensitivity sweep.

**What this gates:** Every VOI number in the project is denominated in whatever this card decides. The
[X-12](X-12%20Tripwire%20if%20the%20headline%20number%20is%20flat.md) stockout-penalty sweep sweeps
this card's stockout-penalty parameter specifically, if B or C is chosen.

**Revisit if:** The [X-12](X-12%20Tripwire%20if%20the%20headline%20number%20is%20flat.md) sensitivity sweep shows the
headline VOI is highly sensitive to the stockout penalty's exact value — that's the signal that this
term deserves a better-grounded estimate than a first guess.

**Depends on:** `X-02`, `MOD-10`

**Milestone:** M3 — VOI sweep, oracles, misspecification arms

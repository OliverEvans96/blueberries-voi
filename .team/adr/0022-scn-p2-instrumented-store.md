# 0022. SCN-P2: Instrumented store
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SCN-P2
GROUP: SCN
PROVENANCE: notes-agree
TIER: 2
AGAINST-RECOMMENDATION: true

## Context

**What the store observes.**

P1, plus everything a determined grocer can buy in 2026 without waiting for Sunrise:

- **Periodic date audits** — a Date Check Pro / Whywaste-style sweep giving a snapshot of the on-shelf
  date distribution, 1–3× per week
- **Markdown scans** — reduced-to-clear events are age-resolved sales by construction, but
  **left-truncated**: you only see them near the sell-by
- **Variable-weight categories are already age-resolved today.** Meat, deli, bakery and prepared foods
  print their own labels carrying a pack date, and those labels are scanned at POS.

**Why in or out.**

That last bullet is the strongest present-day hook in the entire project:

> **There is a category where you can validate the Sunrise-world model today, on data the retailer
> already has.** Nobody built it on purpose and, as far as I can tell, nobody models it.

**Out:** date audits are a distinct observation model (an age histogram with counting error) and cost
a filter variant of their own.

> **Recommended: In** — but the value here is the *argument*, and the argument can be made in prose
> without simulating the audit observation model. Consider In-for-markdown-scans, Out-for-audits.

## Decision

We will adopt **B — Out**. Chosen against the card recommendation of **A — In**.

**B — Out.** ⚑ Against the card's recommendation (A).

## Alternatives considered

- **A — In** _(card recommendation; not chosen)_ — not chosen on the board.

## Consequences

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** Membership of the knowledge ladder changes.

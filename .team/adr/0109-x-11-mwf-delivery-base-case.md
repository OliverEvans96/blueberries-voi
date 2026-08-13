# 0109. X-11 reopen: Mon/Wed/Fri delivery base case (LT=1)

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: X-11
GROUP: X
PROVENANCE: CAL-01 Wave 0 — Oliver reopen of daily cadence
TIER: 1
MILESTONE: CAL-01 — calendar realism
SUPERSEDES: 0011

## Context

ADR [0011](./0011-x-11-delivery-cadence-for-the-base-case.md) locked **daily** delivery
(against the card’s 3×/week recommendation) to keep time-homogeneity. That choice stacked with
order-qty-only VOI and a two-axis sweep in the regime where age information bites least.

Oliver reopened X-11 for milestone **CAL-01**: the scientific base case becomes a realistic berry
cadence. ADR 0011 already listed the three mandatory re-derives when leaving daily delivery:

1. Protection interval becomes **day-indexed**.
2. Age distribution becomes only **periodic**; age-blind baselines need day-indexed survival weight.
3. Rollout horizon sweep must move in **multiples of 7**.

Physics stays **daily** (`day_step` ages / demand / spoil every calendar day). Cadence constrains
**when orders may be placed**, not the tick.

## Decision

We will adopt **Mon / Wed / Fri deliveries** with **lead time = 1 day** as the **new base case**
for simulation, VOI, and the web studio.

- Delivery weekdays: `{0, 2, 4}` (Mon / Wed / Fri).
- Order weekdays: `{6, 1, 3}` (Sun / Tue / Thu) — place the order one day before delivery.
- Non-order days force `order_qty = 0`; full daily physics still runs.
- Calendar epoch remains `2024-01-01` (Monday) + episode day index (same synthetic ASN clock).
- X-06 cadence-as-VOI-axis stays **parked**; this ADR changes the **fixed** base case only.
- Prior citeable VOI numbers under daily cadence are **not** transferable; regeneration is required
  (changelog must say so at closeout).

Schedule API ownership and protection-day formulas live in ADR [0111](./0111-order-schedule-api.md).

## Alternatives considered

- **Keep daily base case (ADR 0011 A)** — rejected: Oliver reopened X-11; daily is the regime where
  age VOI is weakest and understates the post’s claim.
- **Daily base + one 3×/week sensitivity cell (ADR 0011 C)** — rejected: CAL-01 makes weekly
  cadence the default everywhere (sim / VOI / web), not a side cell.
- **Tue/Thu/Sat or other 3× patterns** — rejected: Mon/Wed/Fri is the most common produce truck
  cadence and matches the Fri→Mon protection≈4 story via Thu order → Fri delivery → next Sun order.
- **Collapse physics to weekly ticks** — rejected: spoil / age / demand occur every calendar day;
  only ordering is gated.

## Consequences

**Easy:** protection intervals 3 / 3 / 4 on Sun / Tue / Thu land naturally; UI can jump to the next
order day via existing `step_n`.

**Hard / cost:** every controller, baseline, rollout, M2 gate, burn-in assumption, and VOI smoke
that assumed time-homogeneous daily ordering must be re-derived (Tracks A / D). Prior daily-cadence
headline numbers are invalidated until regenerated.

**Locked in:** MWF delivery, LT=1, order Sun/Tue/Thu, daily physics ticks, X-06 still parked.

**Revisit if:** Oliver reopens X-06 (cadence as a sweep axis) or changes LT / delivery set.

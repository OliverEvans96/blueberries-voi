# 0029. MOD-07: Picking kernel form
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-07
GROUP: MOD
PROVENANCE: contested
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1.*

**The question.**

How shoppers choose among cohorts on the shelf. Your bullets ask for "a one-parameter function to
describe the picking kernel — vary sigma to go from LIFO to random."

**A correction that is worth a line in the post.**

An earlier bullet says the dial runs "LIFO to FIFO". It does not, and it shouldn't:

    1/sigma -> 0   random picking
    1/sigma -> inf strict LIFO

**FIFO is not a customer preference.** Nobody digs to the back for the *oldest* punnet. FIFO is what
the *store* wants, and the store's only lever on it is rotation and facing — which changes what is
*reachable*, not what is *preferred*.

Keeping those separate matters, because it is the reason the kernel exists at all: **in self-service
produce the issuing order is not a control.** That is the assumption almost every perishable
inventory paper makes and this one cannot, and it is a distinction most of the literature elides.

## Decision

We will adopt **A — Survival-power kernel: weight proportional to S(tau)^(1/sigma)**.

**A — Survival-power kernel: weight proportional to S(tau)^(1/sigma).** Chosen on the board.

## Alternatives considered

- **B — Logistic in age** — not chosen. More flexible, unrelated to the physics, two parameters.
- **C — Softmax over age with a temperature parameter** — not chosen. Equivalent to A up to reparameterisation when the score is log-survival.
- **D — No kernel — uniform picking** — not chosen. The degenerate case. Worth having as a switch, not as the model. > **Recommended: A**, with D available as a baseline. Note that A makes appearance and mortality > share a parameter, so a second-order effect appears: customers preferentially buy the **robust** > units (a fresh-looking punnet is one whose clock ran slow), so **picking enriches frailty on the > shelf while mortality depletes it.** The two selection pressures oppose. Almost certainly small, > but worth naming once.

## Consequences

**Depends on:** `MOD-04`

**Milestone:** M1 — filter recovers truth from synthetic P1 data

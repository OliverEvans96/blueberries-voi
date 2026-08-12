# 0026. MOD-04: Spoilage law
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-04
GROUP: MOD
PROVENANCE: notes-agree
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1.*

**The question.**

The constitutive law that turns effective age into a per-unit, per-day death probability. It is the
object the whole post sweeps, so its form is the claim.

**The three slots, so they stop competing.**

| Slot | Object | Stochastic? |
| --- | --- | --- |
| **Clock** | Arrhenius / activation factor. Defines effective age; it is not a *model* of it | No |
| **Constitutive law** | Weibull survival and hazard. Also supplies the picking weight | It *is* a probability |
| **Solver** | The filter | Monte Carlo, by construction |

The deterministic Arrhenius curve is the **mean-field limit**; the Binomial death count is the
**finite-population realisation**. The gap between them is variance, and representing that variance
is the entire reason the filter exists. A lot of 12 units does not lose 12·p overnight; it loses
Binomial(12, p), and at 97% service the decision lives in that difference.

**The trap, which must be a test not a comment.**

Write the one-day death probability as a **survival ratio**:

    p_die(tau) = 1 - S(tau + dtau) / S(tau)

**Never** as `h(tau)·dt`. The product form is a first-order approximation whose error **grows with
beta** — precisely the axis this project sweeps — so a bug here would manufacture or destroy the
headline result. It is also the *easy* mistake, because hazard × timestep is how everyone first
writes a discrete-time survival model.

## Decision

We will adopt **A — Weibull hazard on effective age, conditional survival ratio**.

**A — Weibull hazard on effective age, conditional survival ratio.** Chosen on the board.

## Alternatives considered

- **B — Exponential only (beta = 1)** — not chosen. The industry default. No age dependence in the weight.
- **C — Nonparametric discrete hazard** — not chosen. A free parameter per age bin.

## Consequences

**Milestone:** M1 — filter recovers truth from synthetic P1 data

# 0003. X-03: Date pull in or out
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-03
GROUP: X
PROVENANCE: contested
TIER: 1
AGAINST-RECOMMENDATION: true

## Context

**The question.**

**This is the most consequential open item in the notes and it was decided without you.**
[Updated Plan — Filter, Controller, and Where the Weibull Sits](../../Updated%20Plan%20%E2%80%94%20Filter%2C%20Controller%2C%20and%20Where%20the%20Weibull%20Sits.md) §A.3 removed the printed-date pull
to simplify the model. It admits three consequences, and the second one is severe.

**What dropping it costs.**

1. **It kills the censoring argument.** Your outline's §6 claims β is not estimable below D5 *because
   the pull right-censors the hazard tail*. Remove the pull, and lots run to extinction, and you
   observe the whole tail. So β becomes estimable at low data levels and a load-bearing claim of the
   post evaporates.
2. **It removes the only thing bounding the number of live lots.** The note patches this with an
   invented pruning threshold `n_min`, which is a modelling artefact with no physical referent that
   then leaks into the DP baseline and the filter's cost.
3. **It makes the model single-clock**, which is a real simplification — but the two-clock geometry
   (printed date on the calendar, hazard on effective age) is the most distinctive idea in your
   outline.

## Decision

We will adopt **B — Drop it — sale or death only**. Chosen against the card recommendation of **C — Keep the date pull, drop discretionary culling**.

**B — Drop it — sale or death only.** ⚑ Against the card's recommendation (C). The AI notes' choice. Single clock, simpler model.

## Alternatives considered

- **A — Keep the printed-date pull** — not chosen. Units leave by sale, death, or reaching the printed date.
- **C — Keep the date pull, drop discretionary culling** _(card recommendation; not chosen)_ — not chosen. Realistic removal, but the policy still only chooses orders.

## Consequences

The AI notes' choice. Single clock, simpler model.

**What this gates:** MOD state (whether R_l stays) · FIL lattice size and the L bound · the n_min pruning
threshold · VOI whether the "β unlearnable below D5" claim is reportable.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** The supplier date-offset prior turns out to be the thing nobody can defend — that is the one real
cost of A/C.

**Depends on:** `X-01`

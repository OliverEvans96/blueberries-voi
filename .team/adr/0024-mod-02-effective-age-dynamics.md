# 0024. MOD-02: Effective age dynamics
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-02
GROUP: MOD
PROVENANCE: notes-agree
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1. This is the single most consequential structural decision in the project.*

**The question.**

Your plan says "the randomness all happens at the incoming boundary — assume constant conditions once
in store." That sentence, taken literally, converts the problem from stochastic-process estimation
into **static-parameter-per-lot estimation wrapped in a count filter**. It is worth being explicit
that this is what it does, because almost everything downstream depends on it.

**What A buys.**

Effective age becomes a deterministic flow with a random initial condition:

    tau(t) = tau_in + dtau * (t - t_arrival)

with `dtau` a known constant. So:

- **There is no process noise on age at all.** Only the counts evolve stochastically.
- Uncertainty about age does not accumulate — it **contracts** as sale and death events accrue. This
  is structurally the opposite of the usual filtering problem, and it is why the filter is cheap.
- On a discretised age grid, the transition kernel in the age direction is the **identity matrix**.
  The grid never moves, never needs refining, and never smears, because there is no diffusion to
  smear it. This is what makes [FIL-02](FIL-02%20What%20is%20sampled%20versus%20marginalised.md) possible.

**What A costs.**

**A common offset identifies nothing.** If in-store ageing is constant and known, it adds the same
quantity to every lot. It therefore cannot help you tell lots apart. **All identification of relative
freshness comes from arrival staggering** — from lots being different ages, not from them ageing.

That is a real failure mode, not a technicality: if deliveries are on a rigid cadence and the arrival
prior is tight, lots become nearly exchangeable and the composition posterior collapses to the prior.

## Decision

We will adopt **A — Deterministic flow, random initial condition**.

**A — Deterministic flow, random initial condition.** Tau_in drawn once at arrival; no process noise thereafter.

## Alternatives considered

- **B — Stochastic in-store ageing** — not chosen. A latent daily increment shared across lots.
- **C — Per-lot stochastic ageing** — not chosen. Each lot gets its own random increment each day.

## Consequences

tau_in drawn once at arrival; no process noise thereafter.

**Milestone:** M1 — filter recovers truth from synthetic P1 data

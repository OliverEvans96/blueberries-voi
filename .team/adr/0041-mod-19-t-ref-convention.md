# 0041. MOD-19: T_ref convention
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-19
GROUP: MOD
PROVENANCE: newly-raised
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1. Literature calibration — units of effective age.*

**The question.**

The Arrhenius / Q₁₀ clock needs a reference temperature. Where is it pinned? This is not cosmetic —
it changes whether in-store ageing runs at one effective day per calendar day, and how transit ages
compare to remaining shelf life.

## Decision

We will adopt **A — T_ref = 0 °C (UC Davis optimum)**.

**A — T_ref = 0 °C (UC Davis optimum).** Pins the Arrhenius / Q₁₀ clock to the same optimum-storage
anchor as η_ref, so transit and in-store AF share one absolute scale. Under warmer display temps
([MOD-20](MOD-20%20Numeric%20in-store%20temperature.md)) AF_store > 1 is then a real statement, not a
units convention — which is what the SCN-F2a transit-dominance claim needs.

## Alternatives considered

- **B — Absorb T_ref into display-case temperature** — not chosen. In-store Δτ = 1 day/day by construction — the Controller worked-example convention.

## Consequences

AF_store > 1 whenever the display case is warmer than optimum storage.

**What this gates:** Numeric AF on every leg · whether η_ref = 14 d can be quoted at face value · the SCN-F2a "transit
dominates" derivation · how [MOD-20](MOD-20%20Numeric%20in-store%20temperature.md) enters Δτ.

**Revisit if:** The writeup wants AF_store ≡ 1 as a pedagogical default and the appendix already publishes the
rescaling — then B is a presentational choice with an A-equivalent generator underneath.

**Depends on:** `MOD-02`, `MOD-03`, `MOD-11`

**Milestone:** M1 — filter recovers truth from synthetic P1 data

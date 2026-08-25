# ADR 0146 — Rollout candidate search strategy

## Status

Accepted (T-161)

## Context

CTL-02 rollout evaluates a finite set of case-multiple order candidates around
the damped-SW base quantity. The legacy neighbourhood (`±radius` cases, all
integers in between) is dense: K grows with radius and clusters near the base.

## Decision

Introduce `CandidateSearchConfig` with two modes:

1. **`Neighborhood`** — existing `candidate_orders` behaviour (default).
2. **`StratifiedWide`** — fixed `n_candidates` points on a case lattice over
   `[max(0, base−span), base+span]`, always including `base_q`, with optional
   backfill after dedupe.

Span is `span_cases` when positive, else
`clamp(min_span, ceil(span_fraction × base_cases), max_span)`.

`candidate_case_radius` alone continues to select neighbourhood mode for backward
compatibility. Wide mode is opt-in via `candidate_search_mode=stratified_wide`.

## Consequences

- Rollout CRN pairing unchanged (candidates still share path/day seeds).
- Session / PyO3 wire gains optional search kwargs; studio defaults unchanged.
- Ablation (`experiments/rollout_candidate_ablation.py`) can compare modes before
  flipping the production default.

## Supersedes

Nothing. Extends ADR 0059 / CTL-02 candidate enumeration.

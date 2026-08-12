# 0085. Add pyarrow for Abdella parquet I/O

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: *(repo)*
GROUP: ENG
PROVENANCE: M1 Gate 0 / T-003
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

T-003 vendors Abdella-derived temperature traces from Hugging Face as Parquet
(`NifferLi/cold-chain-strawberry-sensors`). Reading those files without inventing
synthetic fallbacks requires a Parquet reader. ADR 0084 deliberately left pandas
out of the runtime set; numpy alone cannot decode Parquet.

## Decision

Add **pyarrow** as a **runtime** dependency of `blueberries_voi` for loading
vendored Abdella shipment Parquet files under `data/abdella/`.

## Alternatives considered

- **urllib + manual CSV conversion only** — rejected: upstream release is Parquet;
  converting offline still needs a Parquet decoder once.
- **pandas.read_parquet** — rejected for M1: pulls pandas as a heavier transitive
  dependency when pyarrow alone suffices.
- **datasets (Hugging Face)** — rejected as runtime dep: oversized for six local
  files already vendored in-repo.

## Consequences

- `uv sync` installs pyarrow; Gate 0 / arrival-generator code may `import pyarrow`.
- Synthetic temperature paths remain forbidden if files are missing (T-003).

**Depends on:** `0084`, `0078`, `MOD-21`, `X-08`

**Milestone:** M1 — filter recovers truth from synthetic P1 data

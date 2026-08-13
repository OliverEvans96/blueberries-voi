# 0098. Simulator export contract: Snapshot / DayDelta / step_n

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: ENG-01 reopen Wave 0 (boundary protocol from gap analysis)
TIER: 1
MILESTONE: ENG-01 — interactive dual-runtime simulator

## Context

The D3 mockup returns a full `ViewModel` on every `init` / `step` / `setEconomics`, including PnL
series, ghost history, heatmap density, and nested belief grids. That shape is fine in-process and
expensive across Pyodide FFI or HTTP (conversion + transport). Crossing the boundary with nested
`list[list[float]]` via deep `toJs` is a known cost; shipping economics on every tick wastes work
when sliders only need a local reproject.

`ShelfBelief.to_export` today uses nested `age_marginals`. The wire protocol needs a **flat**
belief buffer and a clear ownership split so hosts stay interchangeable.

## Decision

We will:

1. Expose interactive engine I/O as **`Snapshot`** (cold: `init` / `reset`) and **`DayDelta`**
   (hot: each `step` / each element of `step_n`). Payloads are JSON-serialisable dicts (or
   `json.dumps` strings at the worker edge). No `ViewModel`, PnL, economics, ghost, or heatmap
   fields on the Python return path.
2. Provide **`step_n(orders: sequence[int]) → list[DayDelta]`** (or one framed `{deltas: [...]}`)
   so play / fast-forward amortises one RPC / HTTP round-trip.
3. Encode belief for the wire as flat buffers:
   - `lot_counts: list[float]` length `L`
   - `age_marginals: list[float]` length `L * K` (row-major)
   - `tau_grid: list[float]` length `K`
   - `L`, `K: int`
   Nested heatmap `density[][]` is **JS-only**, derived from marginals × counts.
4. **Ownership split (binding):**

   | Concern | Owner | Crosses boundary? |
   |---------|--------|-------------------|
   | Physics, arrivals, CRN, lots, pipeline | Python | Yes (`init`/`step`/`reset`) |
   | RBPF / shelf belief | Python | Yes when filter advances |
   | History window append / drop | Python emits; JS mirrors | Delta only |
   | Economics → PnL / totals / ghost | **JS** | **Never** |
   | Heatmap from marginals | **JS** | No |
   | Config dirty staging | **JS** until `reset` | Config on `init`/`reset` only |
   | Policy `act` | Python | Yes |

5. Prefer serialise-once in Python (`json.dumps` or typed buffers); **avoid deep `toJs`** of nested
   Python structures; never return ViewModel/PnL over the wire.

Module home: `src/blueberries_voi/simulator/` (façade + types). Library `ShelfBelief` may keep
nested lists internally; the **wire** flatten happens at the session boundary.

## Alternatives considered

- **Always return full ViewModel from Python** — rejected: forces PnL/ghost/heatmap across FFI/HTTP
  and duplicates mock anti-pattern at production cost.
- **Protobuf / msgpack as v1 wire** — rejected: JSON is enough at L×K≈24; adds a dep and dual
  tooling before hosts exist.
- **Keep nested `age_marginals` on the wire** — rejected: worst FFI shape; flat buffers match
  Transferable `ArrayBuffer` option later without schema fork.
- **Oracle-only deltas with no belief field ever** — rejected: browser v1 includes filter; omit
  belief only when a demo preset explicitly disables filter updates.

## Consequences

**Easy:** one projector serves Mock / Pyodide / Http adapters; golden fixtures assert forbidden
keys; `setEconomics` never calls the engine.

**Hard / cost:** TS mock and Day shapes must be mapped carefully; flatten/unflatten helpers need
tests; rich DayLog fields must be optional on the delta to keep payloads small.

**Locked in:** Snapshot / DayDelta / step_n; flat belief; JS owns presentation economics; no
ViewModel/PnL on Python returns.

**Revisit if:** measured payload size or FFI cost still dominates under dialed budgets — then
consider Transferable buffers as an additive transport, not a schema replacement.

**Depends on:** ADR [0097](./0097-eng-01-dual-runtime-ap.md), [0092](./0092-controller-belief-api.md)

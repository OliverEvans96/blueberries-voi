# T-090 — acceptance criteria → tests (RED)

## Coverage of acceptance criteria

- Given FlatBelief `L ≈ 2` and `tau_grid` ~`0..8`, `beliefGridFromFlat` x-domain
  (`tau_edges`) is age days on that span — **not** `[0, L]`
  → `web/src/engine/projector.test.ts::beliefGridFromFlat age×count rebin (T-090 / ADR 0109) > tau_edges domain follows tau_grid age span (~0..8), not lot-index [0, L]`
  — currently failing: `tau_edges` is lot-index `[0,1,2]` instead of `centersToEdges(tau_grid)`

- `BeliefGrid.density` shaped **`K × C`**; `tau_edges === centersToEdges(tau_grid)`
  (length `K+1`); `count_edges` integer-friendly `0..max(n_l, truth n, 1)`
  → `… > density is shaped K×C (age bins × count bins), not L×K`
  — currently failing: density length `L=2` not `K=4`
  → `… > count_edges are integer-friendly from 0 through max(n_l, truth n, 1)`
  — currently failing: `count_edges` still derived from `tau_grid` (first edge ≠ `0`;
  truth `n` ignored)
  → `… > tau_edges domain…` also asserts `tau_edges` length / equality to
  `centersToEdges(tau_grid)`

- Rebin deposits each lot’s mass into the count bin for `n_l` (nearest-integer when
  non-integer)
  → `… > deposits each lot’s mass into the nearest-integer count bin for n_l`
  — currently failing: density still `L×K` (length `2` not `K=3`); no count-bin deposit

- Merged age marginal `m` length `K`; `Σ m ≈ Σ lot_counts` when rows normalize
  → `web/src/engine/projector.test.ts::ageMarginalFromFlat (T-090) > returns length-K merged age mass; sum equals Σ lot_counts when rows normalize`
  — currently failing: `ageMarginalFromFlat` not exported (`typeof` is `undefined`)

- Age-marginal chart x-domain matches heatmap `tau_edges`; mounts as **top** marginal
  above Belief heatmap
  → `web/src/sections.belief.test.ts::Belief section contracts (T-090) > main.ts mounts age-marginal above the Belief heatmap (source order)`
  — currently failing: no `beliefAgeMarginal` / `renderBeliefAgeMarginal` import in `main.ts`
  → `… > ships beliefAgeMarginal chart module sharing tau / age domain with heatmap`
  — currently failing: `web/src/charts/beliefAgeMarginal.ts` missing
  → projector age-marginal test also asserts `m.length === tau_edges.length - 1`
  (shared age-bin count) once the export exists

- Truth overlay markers at `(lot.tau, lot.n)` on the same age×count scales (no lot-index x)
  → `… > truth (tau, n) land on the same age×count scales as rebinned cells`
  — currently failing: `tau_edges` upper bound is `L=2` (lot-index), not age span
  → `… > ships beliefAgeMarginal…` also asserts `beliefAgeCount.ts` places markers via
  `x(d.tau), y(d.n)` (source contract; runs after the module exists)

- Belief section `plotIds` include age-marginal + heatmap; blurb mentions age×count vs
  truth and the age marginal
  → `… > plotIds include age-marginal and heatmap plot ids`
  — currently failing: only `["plot-belief-lg"]` (length 1)
  → `… > blurb mentions age×count belief vs truth and the age marginal`
  — currently failing: blurb has age×count/truth but not “marginal”

- No Python / wire FlatBelief shape change (`age_marginals` stays `L*K`)
  → Not a new RED surface (adapters already assert flat `L*K`). Verify by keeping
  `mockAdapter.daydelta` / HTTP / Pyodide flat-belief tests green without schema edits.
  Optional boundary covered by `returns empty density for L=0` (still green on current stub).

- Vitest covers projector rebin + age-marginal; T-054 `L×K` / lot-index tests superseded
  → Replaced former `densityFromFlatBelief` `L×K` describe block with the
  `beliefGridFromFlat age×count rebin` + `ageMarginalFromFlat` suites above.

## Not covered by tests

- Exact plot element id string (`plot-belief-age-marginal` vs similar) — open in spec;
  tests accept any id matching `/age[-_]?marginal|marginal/i` plus a heatmap id.
- Full DOM / D3 pixel layout of the top strip — Node vitest has no jsdom; source
  order + module presence + projector vectors are the RED gate. Verify visually after
  implement.
- Python export / FFI suite — AC is “remain green without schema edits”; no new
  pytest RED. Verifier / implement should not touch Python wire.

## RED command

```bash
cd web && npx vitest run src/engine/projector.test.ts src/sections.belief.test.ts
```

# T-087 RED map — Demand UI (DOW profile / protection coverage)

## Coverage of acceptance criteria

- Demand UI renders a DOW profile (seven-day means/factors) from Snapshot
  `demand_summary`, not a decorative unrelated sinusoid unmarked as non-physics  
  → `web/src/charts/demandUi.test.ts` › demand chart module exposes a length-7
  DOW series from DemandSummary — currently failing: missing
  `dowSeriesFromDemandSummary` (or alias) on `demandDist` / successor  
  → `…` › demandDist (or successor) reads demand_summary / dow_means — currently
  failing: chart source still μ-only `demandPmf`, no `dow_means`  
  → `…` › main.ts wires demand chart with demand_summary — currently failing:
  `renderDemandDist(els.demand, vm.config, …)` only  
  → `…` › mock generate.ts Math.sin seasonal factor is absent or marked
  non-physics — currently failing: unmarked `Math.sin` in `sampleDemand`  
  → `…` › μ-only demandDist PMF is replaced by DOW profile or marked
  non-physics — currently failing: unmarked i.i.d. `demandPmf` chart

- Protection-interval coverage shown for order days (3 / 3 / 4 on Sun/Tue/Thu)
  using schedule fields  
  → `…` › exports protection coverage for order days Sun/Tue/Thu as 3/3/4 —
  currently failing: missing `protectionCoverageFromSchedule` (or alias)  
  → `…` › Demand UI source or markup includes protection labels — currently
  failing: no 3/3/4 / Sun–Tue–Thu protection chrome in chart/main/sections

- Sales/demand charts that assume i.i.d. daily μ-only are updated or clearly
  marked non-physics / removed  
  → `…` › μ-only demandDist PMF … — currently failing (see above)  
  → `…` › salesDemand chart is DOW-aware, history-only, or marked non-physics —
  **passing** (history lines only; no invented μ sinusoid)

- Mock adapter supplies enough stub profile data for charts in mock mode  
  → `…` › init Snapshot demand_summary has scale_mu and length-7 dow_means —
  **passing** (T-085 tip)  
  → `…` › init Snapshot schedule order_weekdays are Sun/Tue/Thu — **passing**

- Web unit/smoke asserts DOW series length 7 and protection labels present  
  → `…` › contract: DOW series length is 7 and protection map is 3/3/4 — currently
  failing: DOW length assert would pass via mock, but
  `protectionCoverageFromSchedule` missing (smoke incomplete)

- No new runtime Python deps; no HF in browser path  
  → `…` › web package.json … no huggingface / transformers / datasets —
  **passing** (guard)  
  → `…` › web/src does not import Hugging Face datasets — **passing**  
  → `…` › pyproject core runtime deps stay free of datasets / HF — **passing**

## Proven RED

```text
# From .worktrees/T-087-qa on team/T-087/qa
cd web && pnpm install
./node_modules/.bin/vitest run src/charts/demandUi.test.ts
# 8 failed, 6 passed — failures are missing DOW/protection Demand UI wiring and
# unmarked decorative sinusoid / μ-only PMF (not import typos). Mock stubs + HF
# guards already green from T-085 tip.
```

## Not covered by tests

- Exact D3 mark choices / visual polish (spec open question) — verify by visual
  smoke once implement lands DOW + protection chart.
- Next-order-day control (T-086) and VOI closeout (T-088).
- Full suite / coverage ≥80% — verifier owns CI-parity gates.
- Live Pyodide/HTTP Snapshot threading of `demand_summary` into ViewModel —
  covered once main/projector consume Snapshot fields; mock + chart contracts
  are the C3 RED surface.

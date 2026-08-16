# 0099. ENG-01 reopen: dual runtime A′ (Pyodide prod + API dev)

STATUS: ACCEPTED (amended by 0120: third adapter `wasm`; Pyodide retained)
DATE: 2026-08-12
BOARD-ID: ENG-01
GROUP: ENG
PROVENANCE: Oliver reopen 2026-08-12 (supersedes 0073 option C)
TIER: 1
MILESTONE: ENG-01 — interactive dual-runtime simulator

## Context

ADR [0073](./0073-eng-01-browser-simulator-scope.md) locked **C — static figures only**, parking
live browser inference because production-N ResearchParticleFilter plus full rollout is not interactive in a tab.
That lock blocked packaging, façade, and D3 integration even after M1–M3 left a library shaped for
handoff ([M2 controller brief](../plans/M2-controller-agent-brief.md)).

Oliver reopened ENG-01 with an explicit dual-runtime product: **Pyodide is the production
interactive host**; **an HTTP API is the development host**; both call one Python library surface.
This is **not** a full WASM rewrite of the filter (option A) and **not** JS-only physics with
pre-baked JSON as the production engine (option B). Browser v1 must run **sim + filter +
controller** under **dialed budgets**, not production particle counts.

## Decision

We will:

1. **Supersede ADR 0073.** ENG-01 target is **A′ dual runtime**: shared `EngineSession` library;
   **Pyodide worker = prod** interactive path; **ASGI API = dev** path; D3 mockup
   (`web/d3-simulator-mockup`) is the presentation consumer in a later slice.
2. **Ship order (binding):** Slice 1 common + Pyodide → Slice 2 API → Slice 3 D3 mockup wiring.
3. **Browser v1 compute:** live `day_step` + ResearchParticleFilter + controller `act` with first-class budget knobs
   (e.g. demo presets such as `N≤200`, `H≤7`, `n_rollout_paths≤2`, candidate radius 1). Desktop /
   CI retain full budgets via the same API.
4. **Pin runtimes:** document **Pyodide 314.0.4** / **CPython 3.14.2** for the browser wheel ABI;
   add **3.14** to CI; keep **3.11** and **3.12** for native / API until a separate drop decision.
5. **Scope:** ADR/export contract, façade, packaging, hosts, and UI adapters are all in ENG-01
   (ticketed T-042–T-058). Honesty / cadence ⚑ cards stay out.

Related contracts: export ADR [0100](./0100-simulator-export-contract.md), packaging
[0101](./0101-eng-01-packaging-pyodide-wheels.md), API [0102](./0102-eng-01-api-asgi-session.md).

## Alternatives considered

- **Keep 0073 C (static only)** — rejected: Oliver explicitly reopened ENG-01 for interactive
  dual-runtime work.
- **Full WASM port of filter/rollout (option A)** — rejected: multi-runtime rewrite with little
  reader-visible payoff; library already targets Python (X-09).
- **JS-only forward sim + pre-baked JSON (option B) as production engine** — rejected: fake
  physics in the mockup must not remain the production interactive path; B may still inform
  static VOI figure exports elsewhere.
- **API-only interactive host (no Pyodide)** — rejected: prod path must run in-browser for the
  blog demo without requiring a always-on backend for readers.
- **Pyodide-only (defer API forever)** — rejected: Oliver locked API as first-class **dev** host
  sharing the same schema (implement after Slice 1).

## Consequences

**Easy:** one Python façade serves worker and HTTP; D3 projector stays host-agnostic; M2 budget
knobs and `ShelfBelief` export become the browser path without a second CTL API.

**Hard / cost:** packaging must shed pyarrow/matplotlib on the browser install; CI gains a 3.14
matrix leg and Release wheel pipeline; demo budgets must stay honest so readers do not confuse
dialed-N inference with production VOI claims.

**Locked in:** A′ dual runtime; Pyodide=prod / API=dev; slice order; sim+filter+controller under
budgets; Pyodide 314.0.4 / CPython 3.14.2 pin; not A and not B-as-prod.

**Revisit if:** Pyodide ABI or micropip cannot install the slim wheel on 314, or interactive
latency under dialed budgets is still unusable — then re-scope browser compute (not silently
return to 0073 C without Oliver).

**Depends on:** `X-09`, `FIL-01`, `CTL-02`, ADR 0092 (`ShelfBelief`), M2/M3 library tips

**Supersedes:** [0073](./0073-eng-01-browser-simulator-scope.md)

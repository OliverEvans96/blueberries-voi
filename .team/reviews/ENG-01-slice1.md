# ENG-01 Slice 1 close-out (T-048)

DATE: 2026-08-12  
STATUS: APPROVED  
TICKETS: T-043–T-047 (close-out T-048)  
ROLE: implement (close-out DoD)

## Scope

Slice 1 (common + Pyodide / browser-worker path) is complete for tickets
**T-043 through T-047**. Reviews APPROVED and verify PASS artifacts are on this tip.
Landing on `main` is a human decision — agents did not merge.

## Definition of done

- [x] T-043 EngineSession + day driver verify-green
- [x] T-044 derived Abdella + browser extras verify-green
- [x] T-045 golden Snapshot / DayDelta fixtures verify-green
- [x] T-046 slim wheel + Release + micropip smoke verify-green
- [x] T-047 Pyodide worker RPC + budget smoke verify-green
- [x] Client-voice changelog for Slice 1
- [x] Plan Slice-1 waves marked complete
- [x] Slice-1 complete pending human merge (no agent merge to `main`)

## Non-goals (binding — still hold)

- [x] No full WASM rewrite — Slice 1 is not a WASM rewrite of the simulator
- [x] No matplotlib / pyarrow in the browser path
- [x] No production-N-in-tab claim (no production-N / N=2000 particles claim without dials)
- [x] API / ASGI implement not required for Slice-1 DONE (Slice 2 / HTTP is out of scope here)

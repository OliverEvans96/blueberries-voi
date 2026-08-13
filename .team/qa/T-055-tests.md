## Coverage of acceptance criteria

- `PyodideAdapter` implements `EngineAdapter` and forwards to the worker RPC  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter implements EngineAdapter > constructs with workerUrl, wheelUrl, and optional budgets` — currently passing (method surface)  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter implements EngineAdapter > spawns a Worker from workerUrl and communicates the Release wheelUrl` — currently failing: stub does not construct Worker / pass wheelUrl  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter implements EngineAdapter > forwards init / step / step_n / reset / act as worker RPC and returns Snapshot/DayDelta` — currently failing: no Worker / empty RPC results

- Adapter never holds a PyProxy on the main thread; only plain data / JSON  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter main-thread plain data (no PyProxy) > source never calls runPython / loadPyodide on the main thread` — currently failing: missing `new Worker` / `.postMessage(` / `JSON.parse|stringify` in code  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter main-thread plain data (no PyProxy) > returns structured-clone / JSON-safe plain objects from RPC results` — currently failing: Worker not constructed

- `init` / `step` / `step_n` / `reset` (/ `act`) return Snapshot/DayDelta parsed for the projector  
  → `… > forwards init / step / step_n / reset / act …` (above)  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter main-thread plain data (no PyProxy) > Snapshot / DayDelta omit presentation keys for the projector` — currently failing: stub returns `{}` instead of Snapshot/DayDelta

- Integration smoke: load Release wheel URL (or fixture wheel) under Pyodide 314.0.4 and complete one init+step  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter integration smoke … > packaging worker pins Pyodide 314.0.4 and Release/slim wheel install` — currently passing (T-047 artifact)  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter integration smoke … > ships a clear pass/fail smoke that drives PyodideAdapter init+step` — currently failing: no adapter smoke script/export

- Demo budget preset is the default for this adapter  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter demo budget defaults > DEFAULT_DEMO_BUDGETS matches ADR 0097 dialed caps` — currently passing  
  → `web/src/engine/pyodideAdapter.test.ts::PyodideAdapter demo budget defaults > init uses DEMO_BUDGETS by default when budgets opts are omitted` — currently failing: dialed config not posted on init RPC

## Not covered by tests

- Live CI download of Pyodide 314 + published Release `.whl` — verify via the implementer’s
  pass/fail smoke script (existence asserted); FakeWorker covers contract locally.
- HttpAdapter (T-056) — out of scope for T-055.
- Studio default engine switch (T-057).

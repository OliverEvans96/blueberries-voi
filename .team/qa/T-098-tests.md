# T-098 — acceptance criteria → tests (RED)

## Command (focused Vitest)

```bash
cd /home/oliver/blog/blueberries-voi/.worktrees/T-098-qa/web \
  && npm test -- src/engine/actOpts.test.ts
```

Result: **8 failed | 1 passed** (9 total). Failures are assertion misses on missing typed exports / normalize / `MockAdapter.act` — not import errors.

## Coverage of acceptance criteria

- `web/src/engine/types.ts` exports typed `ActOpts` (not only `Record<string, unknown>`) with optional `policy` and ADR 0112 budget fields (`alpha`, `rho`, `H`, `n_rollout_paths`, `candidate_case_radius`, `n_particles`, `order_qty` / `q`)
  → `web/src/engine/actOpts.test.ts::Typed ActOpts (T-098 / ADR 0112) > exports ActPolicyName, ActBudgets, and typed ActOpts (not only Record)`
  — currently failing: no `ActPolicyName` / `ActBudgets`; `ActOpts` is still `Record<string, unknown>`
  → `… > caller-facing ActOpts compiles at use sites (policy + nested/flat budgets)`
  — currently passing (runtime smoke with today’s `Record` alias; typed export gated by the source-scan test above)

- Shared normalizer produces HTTP `{ policy?, budgets }` (no flat budget siblings) and Pyodide flat `{ policy?, alpha?, … }`
  → `…::HttpAdapter.act nests budgets under POST body (T-098) > folds flat + nested knobs into { policy?, budgets } with no flat budget siblings`
  — currently failing: flat `alpha: 0.9` not folded into `budgets` (only nested `rho`/`H`/… appear)
  → `… > accepts the same caller ActOpts shape as Pyodide (flat order_qty folds into budgets)`
  — currently failing: flat `order_qty: 24` dropped (`budgets.order_qty` / `q` undefined)
  → `…::PyodideAdapter.act uses flat worker params (T-098) > flattens policy + budget knobs (no nested budgets object on the wire)`
  — currently failing: worker params still include nested `budgets` (raw opts spread)
  → `…::Shared normalize surface (T-098) > adapters (or a shared helper) encode nest vs flat from one caller shape`
  — currently failing: `PyodideAdapter.act` still `call("act", { ...(opts ?? {}) })` without flattening

- `HttpAdapter.act` uses nested shape; `PyodideAdapter.act` uses flat shape; both accept the same caller-facing `ActOpts`
  → HTTP + Pyodide tests above (same `CALLER_OPTS` / flat `order_qty` caller shapes)

- `MockAdapter.act(opts?: ActOpts)` returns a `DayDelta`, advances one mock day (seq / episode_day), chooses order from opts
  → `…::MockAdapter.act returns DayDelta (T-098) > exists, advances one mock day, and chooses order from opts`
  — currently failing: `typeof adapter.act === "undefined"` (method missing)

- Vitest asserts typed opts; HTTP nests budgets; Pyodide flat; MockAdapter.act DayDelta without forbidden presentation keys
  → typed / HTTP / Pyodide tests above
  → `…::MockAdapter.act returns DayDelta (T-098) > act DayDelta omits forbidden presentation keys`
  — currently failing: `act` missing (cannot assert payload yet)

- Mock heuristic documented as **not** numeric-parity with Python `rollout_order` / `DampedSurvivalWeightedPolicy`
  → `… > documents that mock act is not numeric-parity with Python rollout / damped SW`
  — currently failing: no `act(` in `web/src/mock/adapter.ts` (and no parity disclaimer)

## Not covered by tests

- Exact mock heuristic formula for `damped_sw` / `rollout` (beyond “returns DayDelta / advances day / uses constant `order_qty`”) — because AC allows any documented UI heuristic; verify by reading the implementer comment + smoke Play.
- End-to-end Autopilot Play chrome / Controller section — T-099 / T-100 (out of scope).
- Python `_select_order` / numeric parity with mock — explicitly non-goal (T-097 / ADR 0112).

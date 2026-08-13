# T-101 — acceptance criteria → proof map (close-out)

Close-out ticket: no new product features. QA provides a runnable Autopilot mock
smoke harness plus this criterion map. Implement owns smoke evidence + changelog;
verify owns Python CI-parity gates + web vitest + `.team/qa/T-101.md` verdict.

## Coverage of acceptance criteria

- Smoke evidence file `.team/qa/T-101-smoke.md` records ≥3 Autopilot Play ticks
  under mock adapter with Controller policy `damped_sw` (DayDelta-driven UI),
  and/or HTTP/Pyodide `act` + `rollout` under DEMO_BUDGETS without overlapping
  calls; fake-only unit tests alone do not replace the smoke note when a live
  host path is available
  → **Harness (qa):** `web/scripts/smoke-autopilot-mock.ts` via
    `cd web && npm run smoke:autopilot` — Autopilot + `MockAdapter.act` with
    `policy: "damped_sw"` for ≥3 ticks, asserts advancing `episode_day` /
    `seq`, `day.order_qty`, and no overlapping `act`
  → **Evidence (implement):** write `.team/qa/T-101-smoke.md` documenting host
    used (mock studio / HTTP / Pyodide), command(s), and observed ticks / UI
    updates (or HTTP act+rollout). Prefer mock or HTTP if Pyodide wheel is heavy.
  → currently RED for close-out DoD: **smoke evidence file absent** on this tip
    (`test -f .team/qa/T-101-smoke.md` → missing). Harness itself is runnable
    against merged T-100 Autopilot; exit non-zero if the path regresses.

- `.team/changelog.md` gains a plain-English Autopilot entry (client voice: no
  file paths as the lead) — studio can Autopilot-play day by day with controller
  policy knobs and pause safely
  → **Implement / write-changelog:** append entry under `.team/changelog.md`
  → currently RED: no Autopilot / T-101 client-voice close-out line yet (verify
    by reading changelog + review client-voice rules)
  → QA does **not** write the changelog.

- Python side (T-097): verify on **Python 3.11** with CI-identical argv after
  `pip install -e ".[dev]"` (or uv same argv on 3.11); verdict in
  `.team/qa/T-101.md`
  → **Verify:**
    ```bash
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    ruff check .
    ruff format --check .
    mypy src tests
    pytest -n auto --cov=blueberries_voi --cov-branch \
      --cov-report=term-missing --cov-report=xml --cov-fail-under=80
    ```
  → Record PASS/FAIL + failing command in `.team/qa/T-101.md` (verifier only;
    do **not** use `ruff format .` as the gate).

- Web side: `vitest` green for Autopilot / ActOpts / Controller tests from
  T-098–T-100; noted in `.team/qa/T-101.md`
  → **Verify:** `cd web && npm test` (`vitest run`) — includes
    `actOpts.test.ts`, `sections.controller.test.ts`, `autopilotLoop.test.ts`,
    and this ticket’s `scripts/smoke-autopilot-mock.ts` when run via
    `npm run smoke:autopilot` (also safe to include in full `npm test` if
    vitest picks it up by path / config)
  → Note results in `.team/qa/T-101.md`.

- `.team/qa/T-101.md` says **PASS** only if the above gates succeeded on the
  pinned interpreter; otherwise **FAIL** with the failing command
  → **Verify:** write `.team/qa/T-101.md` (never written by qa). PASS requires
    smoke note present, changelog entry present, Python 3.11 CI-parity green,
    web vitest green.

## Not covered by tests

- Manual studio chrome click-through (Play / Pause / order slider sync visuals)
  — harness covers `createAutopilotLoop` + `MockAdapter.act` DayDelta ticks;
  implement may note UI observation in `T-101-smoke.md`.
- Live HTTP `damped_sw` then `rollout` under DEMO_BUDGETS without overlapping
  calls — optional alternate smoke path per spec open question; document in
  `T-101-smoke.md` if used instead of (or in addition to) mock Autopilot.
- Live Pyodide host smoke — optional / prefer mock+HTTP if wheel is heavy;
  document host choice in smoke note.
- Changelog client-voice wording polish — implement + reviewer (client-voice
  skill); qa only maps the requirement.

## RED / harness commands (qa)

```bash
# Autopilot mock smoke (≥3 damped_sw ticks) — exit non-zero if path broken
cd web && npm install && npm run smoke:autopilot

# Close-out artifacts still missing on qa tip (implement owns these)
test -f .team/qa/T-101-smoke.md   # expect: missing until implement
# changelog Autopilot / T-101 entry: expect absent until implement
# .team/qa/T-101.md: verify only — must not exist on qa tip
```

## RED evidence (qa worktree)

```
cd web && npm run smoke:autopilot
→ Test Files  1 passed (1) / Tests  1 passed (1) / exit 0
```

Harness is green against merged T-097–T-100 Autopilot + MockAdapter (proves ≥3
`damped_sw` ticks, advancing seq/episode_day, `day.order_qty`, no overlapping
`act`). Close-out DoD remains RED until implement:

- `.team/qa/T-101-smoke.md` — **absent**
- Autopilot changelog line — **absent**
- `.team/qa/T-101.md` — **must remain absent** (verifier)

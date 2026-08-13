# In-flight ticket / ADR reservations (2026-08-13)

Prevents ID collisions between concurrent agents. Update or delete when streams land on `main`.

| Stream | Tickets | ADRs | Branch tip (as of lock) | Notes |
|--------|---------|------|-------------------------|--------|
| **Arrival-only filter** | **T-067**–**T-069** | **0105**–**0106** | `team/T-067/architect` @ `1fbd931` | Plan: [arrival-only-count-filter.md](./arrival-only-count-filter.md). Do not renumber. |
| **ENG-01 dual-mode readiness** | **T-070**–**T-075** | **0107**–**0108** | `team/ENG-01-readiness/wave2` | Done pending human merge. Plan: [ENG-01-readiness.md](./ENG-01-readiness.md). |
| **CAL-01 calendar realism** | **T-076**–**T-088** | **0112**–**0116** | `team/T-088/integrate-main` | Done pending human merge. Plan: [CAL-01-calendar-realism.md](./CAL-01-calendar-realism.md). Oliver reopened X-11 / MOD-09. |
| **Pyodide module-worker** | **T-092** | **0111** | landed on local `main` | **Not** Autopilot. |
| **Studio Autopilot Mode** | **T-091**, **T-097**–**T-101** | **0117** | `team/studio-autopilot/wave` (merge tip `1b755fe`) | Done pending human merge. Plan: [studio-autopilot.md](./studio-autopilot.md). Provisional Autopilot ADR 0112 → **0117** at CAL-01 merge. |
| Landed on `main` (context) | …–T-066; ADR **0109**–**0110** (+ CAL-01 / T-092 on local tip) | …–**0116** | `main` | Belief rebin / obs ladder; CAL-01 0112–0116; module-worker 0111. |

**Next free after Autopilot + CAL-01:** tickets **T-102+**, ADRs **0118+**.

**Cancelled / void:**
- `team/ENG-01-readiness/architect` briefly claimed **T-073–T-078** (wrongly treating T-070–T-072 as arrival-only). Use **T-070–T-075**.
- Autopilot user-plan ids **T-076–T-081** and first Autopilot draft **T-092–T-096** / ADR **0111** — do not reuse those Autopilot claims; CAL-01 owns T-076+, Pyodide owns 0111 / T-092.
- Autopilot provisional ADR **0112** void after renumber to **0117** (CAL-01 owns 0112).

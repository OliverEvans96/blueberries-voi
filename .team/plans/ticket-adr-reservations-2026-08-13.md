# In-flight ticket / ADR reservations (2026-08-13)

Prevents ID collisions between concurrent agents. Update or delete when streams land on `main`.

| Stream | Tickets | ADRs | Branch tip (as of lock) | Notes |
|--------|---------|------|-------------------------|--------|
| **Arrival-only filter** | **T-067**–**T-069** | **0105**–**0106** | `team/T-067/architect` @ `1fbd931` | Plan: [arrival-only-count-filter.md](./arrival-only-count-filter.md). Do not renumber. |
| **ENG-01 dual-mode readiness** | **T-070**–**T-075** | **0107**–**0108** | `team/ENG-01-readiness/wave2` | Done pending human merge. Plan: [ENG-01-readiness.md](./ENG-01-readiness.md). |
| **CAL-01 calendar realism** | **T-076**–**T-088** | (stream ADRs) | in-flight worktrees | **Not** Studio Autopilot — do not repurpose for Autopilot. |
| **Pyodide module-worker** | **T-092** | **0111** | `team/T-092/implement` | **Not** Autopilot. |
| **Studio Autopilot Mode** | **T-091**, **T-097**–**T-101** | **0112** | `team/studio-autopilot/wave` (verify `9a1d482` + chore) | Done pending human merge. Plan: [studio-autopilot.md](./studio-autopilot.md). User plan T-076–T-081 collided → these ids. Void draft T-092–T-096 / ADR 0111 for Autopilot. |
| Landed on `main` (context) | …–T-066; ADR **0109**–**0110** | …–**0110** | `main` | Belief rebin / obs scenario ladder on main; do not reuse 0109–0110 for Autopilot. |

**Next free after Autopilot (and other in-flight streams):** tickets **T-102+**, ADRs **0113+** (unless another stream claims first).

**Cancelled / void:**
- `team/ENG-01-readiness/architect` briefly claimed **T-073–T-078** (wrongly treating T-070–T-072 as arrival-only). Use **T-070–T-075**.
- Autopilot user-plan ids **T-076–T-081** and first Autopilot draft **T-092–T-096** / ADR **0111** — do not reuse those Autopilot claims; CAL-01 owns T-076+, Pyodide owns 0111 / T-092.

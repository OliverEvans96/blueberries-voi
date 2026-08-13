# In-flight ticket / ADR reservations (2026-08-13)

Prevents ID collisions between concurrent agents. Update or delete when streams land on `main`.

| Stream | Tickets | ADRs | Branch tip (as of lock) | Notes |
|--------|---------|------|-------------------------|--------|
| **Arrival-only filter** | **T-067**–**T-069** | **0105**–**0106** | `team/T-067/architect` | Plan: arrival-only (on that tip). Do not renumber. |
| **ENG-01 dual-mode readiness** | **T-070**–**T-075** | **0107**–**0108** | `team/ENG-01-readiness/wave2` | Plan: [ENG-01-readiness.md](./ENG-01-readiness.md). Done pending human merge. |
| **CAL-01 calendar realism** | **T-076**–**T-088** | **0109**–**0113** | `team/T-076/architect` | Plan: [CAL-01-calendar-realism.md](./CAL-01-calendar-realism.md). Oliver reopened X-11 / MOD-09. |
| Landed on `main` (context) | …–T-066 | …–0104 | `main` | Highest ADR on `main` before CAL-01 = 0104 (+ readiness 0107–0108 may land separately). |

**Next free after CAL-01 claim:** tickets **T-089+**, ADRs **0114+**.

**Cancelled:** `team/ENG-01-readiness/architect` briefly claimed **T-073–T-078** (wrongly treating T-070–T-072 as arrival-only). That range is void for readiness; **T-076+** is now CAL-01.

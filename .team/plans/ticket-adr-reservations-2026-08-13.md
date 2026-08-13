# In-flight ticket / ADR reservations (2026-08-13)

Prevents ID collisions between concurrent agents. Update or delete when both streams land on `main`.

| Stream | Tickets | ADRs | Branch tip (as of lock) | Notes |
|--------|---------|------|-------------------------|--------|
| **Arrival-only filter** | **T-067**–**T-069** | **0105**–**0106** | `team/T-067/architect` @ `1fbd931` | Plan: [arrival-only-count-filter.md](./arrival-only-count-filter.md) (on that tip). Do not renumber. |
| **ENG-01 dual-mode readiness** | **T-070**–**T-075** | **0107**–**0108** | `team/T-070/architect` (this tip) | Plan: [ENG-01-readiness.md](./ENG-01-readiness.md). Old plan T-067–T-072 / 0105–0106 abandoned. |
| Landed on `main` (context) | …–T-066 | …–0104 | `main` | T-066 = LL re-bench; highest ADR on `main` = 0104. |

**Next free after both reservations:** tickets **T-076+**, ADRs **0109+**.

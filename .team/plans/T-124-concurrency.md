# Concurrency plan — T-124

**Parent tip:** `main`
**Peak parallelism:** 4
**Critical path length:** 10 waves

Studio UX revamp — T-119 audit remediation + IA + comprehension + polish

## Warnings
- task integration-merge: empty files list (cannot detect conflicts)

## Waves

| Wave | Parallel | Tasks |
|------|----------|-------|
| W0 | 1 | architect |
| W1 | 4 | qa-avail, qa-charts, qa-demand, qa-ia |
| W2 | 2 | impl-W1-A, impl-W1-B |
| W3 | 1 | impl-W1-C |
| W4 | 2 | impl-W2-D, impl-W2-F |
| W5 | 1 | impl-W2-E |
| W6 | 4 | impl-W3-G, impl-W3-H, impl-W3-I, impl-W3-J |
| W7 | 3 | impl-W4-K, impl-W4-L, impl-W4-M |
| W8 | 1 | integration-merge |
| W9 | 2 | review, verify |

## Worktree manifest

| Task | Branch | Path |
|------|--------|------|
| `architect` | `team/T-124/architect` | `.worktrees/T-124-architect` |
| `impl-W1-A` | `team/T-124/W1-A-implement` | `.worktrees/T-124-W1-A-implement` |
| `impl-W1-B` | `team/T-124/W1-B-implement` | `.worktrees/T-124-W1-B-implement` |
| `impl-W1-C` | `team/T-124/W1-C-implement` | `.worktrees/T-124-W1-C-implement` |
| `impl-W2-D` | `team/T-124/W2-D-implement` | `.worktrees/T-124-W2-D-implement` |
| `impl-W2-E` | `team/T-124/W2-E-implement` | `.worktrees/T-124-W2-E-implement` |
| `impl-W2-F` | `team/T-124/W2-F-implement` | `.worktrees/T-124-W2-F-implement` |
| `impl-W3-G` | `team/T-124/W3-G-implement` | `.worktrees/T-124-W3-G-implement` |
| `impl-W3-H` | `team/T-124/W3-H-implement` | `.worktrees/T-124-W3-H-implement` |
| `impl-W3-I` | `team/T-124/W3-I-implement` | `.worktrees/T-124-W3-I-implement` |
| `impl-W3-J` | `team/T-124/W3-J-implement` | `.worktrees/T-124-W3-J-implement` |
| `impl-W4-K` | `team/T-124/W4-K-implement` | `.worktrees/T-124-W4-K-implement` |
| `impl-W4-L` | `team/T-124/W4-L-implement` | `.worktrees/T-124-W4-L-implement` |
| `impl-W4-M` | `team/T-124/W4-M-implement` | `.worktrees/T-124-W4-M-implement` |
| `integration-merge` | `team/T-124/integration-merge` | `.worktrees/T-124-integration-merge` |
| `qa-avail` | `team/T-124/qa` | `.worktrees/T-124-qa-avail` |
| `qa-charts` | `team/T-124/qa` | `.worktrees/T-124-qa-charts` |
| `qa-demand` | `team/T-124/qa` | `.worktrees/T-124-qa-demand` |
| `qa-ia` | `team/T-124/qa` | `.worktrees/T-124-qa-ia` |
| `review` | `team/T-124/review` | `.worktrees/T-124-review` |
| `verify` | `team/T-124/verify` | `.worktrees/T-124-verify` |

## Mermaid

```mermaid
flowchart TB
  architect["architect<br/>W0"]
  style architect fill:#e3f2fd
  qa-avail["qa-avail<br/>W1"]
  style qa-avail fill:#bbdefb
  qa-ia["qa-ia<br/>W1"]
  style qa-ia fill:#bbdefb
  qa-demand["qa-demand<br/>W1"]
  style qa-demand fill:#bbdefb
  qa-charts["qa-charts<br/>W1"]
  style qa-charts fill:#bbdefb
  impl-W1-A["impl-W1-A<br/>W2"]
  style impl-W1-A fill:#90caf9
  impl-W1-B["impl-W1-B<br/>W2"]
  style impl-W1-B fill:#90caf9
  impl-W1-C["impl-W1-C<br/>W3"]
  style impl-W1-C fill:#64b5f6
  impl-W2-D["impl-W2-D<br/>W4"]
  style impl-W2-D fill:#42a5f5
  impl-W2-E["impl-W2-E<br/>W5"]
  style impl-W2-E fill:#2196f3
  impl-W2-F["impl-W2-F<br/>W4"]
  style impl-W2-F fill:#42a5f5
  impl-W3-G["impl-W3-G<br/>W6"]
  style impl-W3-G fill:#1e88e5
  impl-W3-H["impl-W3-H<br/>W6"]
  style impl-W3-H fill:#1e88e5
  impl-W3-I["impl-W3-I<br/>W6"]
  style impl-W3-I fill:#1e88e5
  impl-W3-J["impl-W3-J<br/>W6"]
  style impl-W3-J fill:#1e88e5
  impl-W4-K["impl-W4-K<br/>W7"]
  style impl-W4-K fill:#1976d2
  impl-W4-L["impl-W4-L<br/>W7"]
  style impl-W4-L fill:#1976d2
  impl-W4-M["impl-W4-M<br/>W7"]
  style impl-W4-M fill:#1976d2
  integration-merge["integration-merge<br/>W8"]
  style integration-merge fill:#e3f2fd
  review["review<br/>W9"]
  style review fill:#bbdefb
  verify["verify<br/>W9"]
  style verify fill:#bbdefb
  architect --> qa-avail
  architect --> qa-ia
  architect --> qa-demand
  architect --> qa-charts
  qa-avail --> impl-W1-A
  qa-demand --> impl-W1-B
  qa-avail --> impl-W1-C
  qa-charts --> impl-W1-C
  impl-W1-A --> impl-W1-C
  qa-ia --> impl-W2-D
  impl-W1-C --> impl-W2-D
  qa-ia --> impl-W2-E
  impl-W1-C --> impl-W2-E
  impl-W2-F --> impl-W2-E
  qa-ia --> impl-W2-F
  impl-W1-C --> impl-W2-F
  impl-W2-D --> impl-W3-G
  impl-W2-E --> impl-W3-G
  impl-W2-F --> impl-W3-G
  impl-W2-D --> impl-W3-H
  impl-W2-E --> impl-W3-H
  impl-W2-F --> impl-W3-H
  impl-W2-D --> impl-W3-I
  impl-W2-E --> impl-W3-I
  impl-W2-F --> impl-W3-I
  impl-W2-D --> impl-W3-J
  impl-W2-E --> impl-W3-J
  impl-W2-F --> impl-W3-J
  impl-W3-G --> impl-W4-K
  impl-W3-H --> impl-W4-K
  impl-W3-I --> impl-W4-K
  impl-W3-J --> impl-W4-K
  impl-W3-G --> impl-W4-L
  impl-W3-H --> impl-W4-L
  impl-W3-I --> impl-W4-L
  impl-W3-J --> impl-W4-L
  impl-W3-G --> impl-W4-M
  impl-W3-H --> impl-W4-M
  impl-W3-I --> impl-W4-M
  impl-W3-J --> impl-W4-M
  impl-W4-K --> integration-merge
  impl-W4-L --> integration-merge
  impl-W4-M --> integration-merge
  integration-merge --> review
  integration-merge --> verify
```

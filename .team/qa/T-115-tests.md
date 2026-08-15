# T-115 — acceptance criteria → tests

**Superseded by verify PASS:** [T-115.md](./T-115.md) (`team/T-115/verify`, merge `3ddfd69` on `main`). The RED notes below are a historical qa artifact from the implement round; all mapped AC now have green tests.

**Post-verify gaps (optional, not blocking PASS):** `main.ts` default-off bootstrap / chart-branch integration test — see [truth-vs-belief-audit.md](../reports/truth-vs-belief-audit.md).

---

## Historical RED map (2026-08-14 implement round)

<details>
<summary>Collapsed — for audit trail only</summary>

- Fresh load / `loadShowTruth` / `truthLots` → `showTruth.test.ts` (was RED: missing module; now green)
- Belief overlay gating → `beliefAgeCount.test.ts` (green before wiring)
- Survival / history / arrival `.truth-*` classes → chart tests (partial RED: styling landed)
- Inventory / age belief paths → `inventoryTarget.test.ts` (was RED; now green)
- `belief_history` → `projector.test.ts` (was RED; now green)
- Play chrome switch → `controls.showTruth.test.ts`, `showTruthUi.test.ts` (was RED; now green)
- Belief blurb off-mode → `sections.belief.test.ts` (green throughout)

Engine diff (no wasm/python session edits) — verified by diff in T-115.md, not behavioural test.

</details>

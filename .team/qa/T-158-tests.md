# T-158 RED test map (qa)

| AC | Test file | Criterion |
|----|-----------|-----------|
| AC-1 | `StudioLayout.test.ts` | v7 grid, no tuning row |
| AC-2 | `engineStatus.test.ts`, `StudioLayout.test.ts` | gear beside engine-status |
| AC-3 | `TuningDrawer.test.ts` | dialog open/close, aria |
| AC-4 | `controls.test.ts`, `TuningDrawer.test.ts` | section controls in drawer |
| AC-5 | (implement + studioLogic tests) | keyboard opens drawer |
| AC-8 | (implement CSS + visual) | interleaved 2-col layout |
| AC-9 | `test_studio_release_version.py` | version 0.3.6 |
| AC-10 | `studio-visual-qa.spec.ts`, `studio-smoke.spec.ts` | e2e v7 + drawer |

## RED proof

Run on qa branch before implement:

```bash
cd web && pnpm exec vitest run src/react/TuningDrawer.test.ts src/react/StudioLayout.test.ts --no-coverage
pytest tests/test_studio_release_version.py::test_studio_package_version_is_0_3_6 --no-cov
```

Expected: failures (TuningDrawer missing, v6 layout, version 0.3.5).

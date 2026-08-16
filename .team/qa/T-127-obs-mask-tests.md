# T-127 — RED test map (qa-obs-mask)

## AC-obs-mask

- Module exports → `web/src/obsMask.test.ts::"ships obsMask.ts with maskFor and applyMask"`
- P0/P1/F1/F1s/F2a/F2 mask table → per-scenario `mask_for *` tests
- P2 and B-state errors → `::"mask_for P2 and B-state throw like Rust"`
- applyMask null absent fields → P0 and F2 apply tests

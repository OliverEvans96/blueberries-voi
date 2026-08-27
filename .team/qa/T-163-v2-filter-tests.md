# T-163 v2-filter — RED criterion → test map (qa)

Shard: `v2-filter` on `team/T-163/v2-filter` from `team/T-163/architect` @ `38df6ede`.

## Coverage of acceptance criteria

- **S1.7 — Filter coherence.** Monte Carlo generative `Λ | d` (and `f | d`) mean/variance matches filter `Duration(d)` law within tolerance at `ρ = 0` and at default `ρ` (v2 §2.6, §3.4.7) → `crates/voi_core/tests/t163_v2_filter_coherence.rs::generative_duration_law_matches_filter` — currently failing: at `ρ = 0` generative `Λ | d` has zero variance (deterministic legged baseline); v2 requires trip-mode + hourly-OU spread and matching filter projection.

## Not covered by tests

- (none for this shard — S1.7 fully covered)

## Focused RED command

```bash
cargo test -p voi_core --test t163_v2_filter_coherence -- --nocapture
```

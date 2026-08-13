# Controller design notes for eventual Pyodide (A′)

**Status:** parked guidance — not a ticket; not ENG-01 reopen  
**Date:** 2026-08-12  
**Audience:** agent implementing M2 controller / rollout  
**Scope:** only constraints that matter so CTL can later run under Pyodide on the Astro site. Full CTL product decisions remain in ADRs 0004 / 0058–0063.

Browser A′ itself stays on the [backlog](../backlog.md) until ENG-01 (ADR 0073) is reopened. These notes exist so M2 does not paint the package into a desktop-only corner.

---

## Do

1. **Keep `controller/` a pure library.** Policies and rollout take belief + params + RNG (+ optional compute budget) and return order quantities / small result dicts. No matplotlib, no parquet/pyarrow, no repo-relative paths, no writing figures or experiment markdown.
2. **Public belief in, JSON-friendly out.** Do not have policies reach into `RBPF._state`. Consume an explicit belief/export type that can be built from the filter *or* an oracle, and that round-trips through lists/floats (worker `postMessage` / `pyodide.FFI` later).
3. **Expose compute budgets as first-class knobs** on rollout / candidate evaluation (`n_rollout_paths`, `H`, particle or sample count used inside rollouts, candidate set size). Desktop experiments use full budgets; a future browser demo dials them down without a second API.
4. **Use existing CRN (`rng.spawn_rng` + named streams).** Add CTL stream constants in `rng.py` as needed. Avoid unseeded global RNG — workers and tests both need bit-stable addressing.
5. **One physics path.** Rollout forward steps call the same `model.day_step` / sim arrival hooks as closed-loop evaluation. No shadow dynamics that would have to be re-ported for WASM.
6. **Stay free of process parallelism.** Prefer sequential rollouts (or a future single-worker chunking scheme). No `multiprocessing` / process pools — they will not map to a browser tab.

## Don’t

1. **Don’t block main-thread assumptions into the API** (e.g. “rollout always runs to production N×H with no budget argument”).
2. **Don’t couple CTL to Abdella file I/O.** Inject shipments or derived arrival products; browser will ship a derived artifact, not parquet.
3. **Don’t put the interactive UI or plotting in this package’s controller path.** Astro/JS (or static images) own presentation; Python returns numbers.
4. **Don’t start Pyodide packaging, GitHub Release wheels, or Astro islands in M2** unless ENG-01 is explicitly reopened — only keep the library shaped for that handoff.

## Handoff when ENG-01 reopens

Expected later work (not M2): slim wheel via CI→GitHub Release, derived Abdella product, thin `init`/`step`/`act` façade, Pyodide worker, no matplotlib in-browser. Controller code written per the **Do** list above should drop into that façade with budget presets only.

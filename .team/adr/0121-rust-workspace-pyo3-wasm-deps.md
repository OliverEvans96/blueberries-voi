# 0121. Cargo workspace and compute-kernel dependencies

STATUS: ACCEPTED
DATE: 2026-08-14
GROUP: ENG
PROVENANCE: Oliver reopen (Rust WASM PyO3 plan)
TIER: 2

## Context

ADR [0119](./0119-rust-compute-kernel-python-host.md) and [0120](./0120-studio-wasm-adapter-third-host.md)
require a native extension and a browser WASM module sharing one kernel. New runtime crates
need an explicit dep lock. Python package layout stays `src/blueberries_voi` (ADR 0077).

## Decision

**Workspace** at repo root (`Cargo.toml`):

| Crate | Kind | Role |
| --- | --- | --- |
| `crates/voi_core` | `rlib` | Physics, WOR DP, day_step, ResearchParticleFilter, episode, VOI cell, session. No Python/JS types. |
| `crates/voi_py` | `cdylib` | PyO3 module **`blueberries_voi._core`**. |
| `crates/voi_wasm` | `cdylib` (wasm) | wasm-bindgen EngineSession RPC. |

**Libraries (v1):**

- Build Python wheels: **maturin** + **pyo3 ~0.29** (`abi3-py311` allowed).
- Browser: **wasm-bindgen** (+ wasm-pack or wasm-bindgen-cli).
- JSON: **serde** / **serde_json**; prefer string JSON on the wire.
- RNG: **rand** + **rand_pcg** (`Pcg64`) + **rand_distr**; WASM entropy: **getrandom** `js`.
- Arrays: **plain `Vec` / `[f64]`** — no ndarray/nalgebra in v1.
- Parallel: **rayon later, feature-gated, off in wasm**. First pass single-thread.

**Python packaging:** prefer mixed maturin so `pip install -e ".[dev]"` still matches CI once
a human copies rustc into live GitHub Actions. Until then, setuptools remains the live backend;
Rust is optional (`[rust]` extra or maturin develop locally). rustc **stable**.

**Non-goals for v1:** Numba, Cython, `wasm32-unknown-emscripten`, bit-identical CRN vs Python.

## Alternatives considered

- **ndarray / nalgebra** — rejected: L is small (ADR 0035); extra WASM size.
- **Separate PyO3 crate without shared `voi_core`** — rejected: would fork physics vs filter
  (violates ADR 0074).
- **Keep setuptools forever and never maturin** — rejected as the long-term mixed layout;
  allowed as a transitional live-CI state until a human updates workflows.

## Consequences

**Easy:** one `cargo test` for kernels; PyO3 and wasm are thin FFI.

**Hard / cost:** rustc on developer and (later) CI images; `target/` gitignored; agents must not
edit `.github/workflows/` — only `packaging/github-workflows/`.

**Locked in:** crate names and dep families above.

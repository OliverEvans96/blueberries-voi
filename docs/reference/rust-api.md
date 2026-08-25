---
title: Rust API (voi_core)
sources:
  code: [crates/voi_core/src/lib.rs, crates/voi_py/src/lib.rs, crates/voi_wasm/src/lib.rs]
---

# Rust API (`voi_core`)

The shared compute kernel is documented with **rustdoc** — API reference
generated from inline `///` comments on the Rust source, covering public
functions, types, and fields (plus key private helpers) across the crate.

Browse the API:

**[Open rustdoc →](/api/rust/voi_core/index.html)**

`voi_core` has no Python or JavaScript in it; two thin wrapper crates expose
it to the rest of the project instead, and each is documented the same way:

- **[`voi_py`](/api/rust/_core/index.html)** — PyO3 bindings, compiled as the
  `blueberries_voi._core` extension module used by notebooks, the CLI, and
  `pytest`.
- **[`voi_wasm`](/api/rust/voi_wasm/index.html)** — a `wasm-bindgen` binding
  compiled to WebAssembly and loaded by the in-browser studio.

A [combined landing page](/api/rust/index.html) links all three crates'
rustdoc together with a short overview of how they fit into the project.

## What's here vs. what's on this site

Rustdoc and this VitePress site answer different questions, and each page's
**In the code** table links between them:

- **Rustdoc** is the API-level reference: what a function does, what it takes
  and returns, and any invariant a caller needs to know — one item at a time,
  browsable by module.
- **This site** is the narrative: the intuition, the math, and — in each page's
  **Why it's modelled this way** section — the modeling choice and the
  alternative it beat. Rustdoc doesn't try to re-argue those choices; it
  points back here instead.

Use rustdoc when you need to know exactly what a symbol does; come back to the
concept pages when you need to know why it exists.

---
title: Rust API (voi_core)
sources:
  code: [crates/voi_core/src/lib.rs, crates/voi_py/src/lib.rs, crates/voi_wasm/src/lib.rs]
---

# Rust API (`voi_core`)

The shared compute kernel — the code that actually runs the simulation and the
filter — is documented with **rustdoc**, the standard Rust documentation
generator. Rustdoc builds an API reference straight from inline `///`
comments in the Rust source, covering every public function, type, and field
(plus a few key private helpers) across the crate.

Browse the API:

**[Open rustdoc →](/api/rust/voi_core/index.html)**

`voi_core` has no Python or JavaScript in it. Two thin wrapper crates expose
it to the rest of the project instead, and each is documented the same way:

- **[`voi_py`](/api/rust/_core/index.html)** — a PyO3 binding (PyO3 is a
  Rust library for building Python extension modules), compiled as the
  `blueberries_voi._core` extension module used by notebooks, the CLI, and
  `pytest`.
- **[`voi_wasm`](/api/rust/voi_wasm/index.html)** — a `wasm-bindgen` binding
  (a tool that generates the glue code needed to call Rust from JavaScript),
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

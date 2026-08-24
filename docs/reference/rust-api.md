---
title: Rust API (voi_core)
sources:
  code: [crates/voi_core/src/lib.rs]
---

# Rust API (`voi_core`)

The shared compute kernel is documented with **rustdoc** — auto-generated API
reference from inline `///` comments on the Rust source, covering public
functions, types, and fields (plus key private helpers) across the crate.

Browse the API:

**[Open rustdoc →](/api/rust/voi_core/index.html)**

## What's here vs. what's on this site

Rustdoc and this VitePress site answer different questions, and each page's
**In the code** table links between them:

- **Rustdoc** is the API-level reference: what a function does, what it takes
  and returns, and any invariant a caller needs to know — one item at a time,
  browsable by module.
- **This site** is the narrative: the intuition, the math, and — in each page's
  **Why it's modelled this way** section — the modeling choice and the
  alternative it beat, sourced from the project's ADRs. Rustdoc doesn't try to
  re-argue those choices; it points back here instead.

Use rustdoc when you need to know exactly what a symbol does; come back to the
concept pages when you need to know why it exists.

//! WebAssembly binding for the browser studio: a single [`handle_rpc`] entry point that
//! forwards JSON-in/JSON-out RPC calls straight through to `voi_core`'s own `handle_rpc`,
//! so the JS/WASM host drives the identical engine session logic used by the native (PyO3)
//! build (ADR 0119).
//!
//! This is one of two thin wrappers around [`voi_core`](../voi_core/index.html), the
//! crate that actually implements the shelf physics, filter, and policy. The other is
//! [`voi_py`](../_core/index.html), which compiles the same kernel as a native Python
//! extension (`blueberries_voi._core`) instead of to WebAssembly -- see `voi_core`'s
//! crate docs for how the whole project fits together, or the [Rust API
//! reference](https://oliverevans.dev/docs/blueberries/reference/rust-api) on the
//! project's narrative documentation site.

use wasm_bindgen::prelude::*;
use voi_core::handle_rpc as core_handle_rpc;

/// Handles one RPC request from the browser studio: takes a JSON request string (`id`,
/// `method`, `params`) and returns a JSON response string. All engine session state lives
/// behind `voi_core`'s own thread-local, so this function is just the `wasm_bindgen`
/// surface -- the actual dispatch, session lifecycle, and error shaping are `voi_core`'s
/// responsibility, kept identical across the native and WASM hosts.
#[wasm_bindgen]
pub fn handle_rpc(request_json: &str) -> String {
    core_handle_rpc(request_json)
}

#[cfg(test)]
mod tests {
    use super::handle_rpc;

    #[test]
    fn init_and_step_return_ok_json() {
        let init = handle_rpc(r#"{"id":"1","method":"init","params":{"seed":1}}"#);
        assert!(init.contains("\"ok\":true"), "init: {init}");
        assert!(
            init.contains("\"lot_counts\""),
            "init Snapshot.belief.lot_counts missing: {init}"
        );
        let step = handle_rpc(r#"{"id":"2","method":"step","params":{"order":0}}"#);
        assert!(step.contains("\"ok\":true"), "step: {step}");
        assert!(
            step.contains("\"lot_counts\""),
            "step DayDelta.belief.lot_counts missing: {step}"
        );
    }
}

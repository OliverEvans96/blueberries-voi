use wasm_bindgen::prelude::*;
use voi_core::crate_name;

/// JSON-in / JSON-out RPC stub (init/step/step_n/reset/act land in a later ticket).
#[wasm_bindgen]
pub fn handle_rpc(request_json: &str) -> String {
    let _ = request_json;
    format!(
        "{{\"id\":null,\"ok\":false,\"error\":{{\"type\":\"Unimplemented\",\"message\":\"{} stub\"}}}}",
        crate_name()
    )
}
